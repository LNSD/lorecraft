"""The one list of rules: every declaration `@rule` registered in a rules package, in code order.

A rule joins the registry by being declared with `@rule` in a module of `lorecraft.rules`; nothing lists the
rules anywhere else. `Registry.load` imports every module of a package, its subpackages included and its unit
tests left out, and keeps the declarations whose module lies in that package outside its unit tests, so a test
that walks a package of sample rules sees only those, and the package's own registry never sees them.

The registry is package data: it reads no workspace and is not a query. A rejection, a code, a name or an alias
code bound twice, is a defect in `lorecraft.rules`, never in the user's repository, so it raises a `RuntimeError`
whose traceback locates the declaration.
"""

import importlib
import pkgutil
from collections.abc import Iterable
from functools import cache
from types import ModuleType
from typing import Final, Self, assert_never

from lorecraft import rules

from .rule import RemovedRule, Rule, RuleDeclaration, declared_rules

_UNIT_TESTS: Final[str] = 'tests'
"""The name of the subpackage beside a package's modules that holds their unit tests, fixed by the unit tier."""


class DuplicateRuleCodeError(RuntimeError):
    """Two declarations share a code: two rules, two removed rules, or a rule and a removed rule.

    Attributes:
        code: The code bound twice, as printed.
        first: The declaration the code was bound to first.
        second: The declaration that bound it again.
    """

    code: str
    first: RuleDeclaration
    second: RuleDeclaration

    def __init__(self, code: str, first: RuleDeclaration, second: RuleDeclaration) -> None:
        self.code = code
        self.first = first
        self.second = second
        super().__init__(f'rule code {code!r} of {second.__qualname__} is already bound to {first.__qualname__}')


class DuplicateRuleNameError(RuntimeError):
    """Two declarations share a name, or a name is spelled as a code.

    Attributes:
        name: The name bound twice.
        first: The declaration the name was bound to first.
        second: The declaration that bound it again.
    """

    name: str
    first: RuleDeclaration
    second: RuleDeclaration

    def __init__(self, name: str, first: RuleDeclaration, second: RuleDeclaration) -> None:
        self.name = name
        self.first = first
        self.second = second
        super().__init__(f'rule name {name!r} of {second.__qualname__} is already bound to {first.__qualname__}')


class DuplicateAliasCodeError(RuntimeError):
    """An alias code is listed twice, or is spelled as a code or a name.

    Attributes:
        code: The alias code bound twice, as printed.
        first: The declaration the alias code was bound to first.
        second: The declaration that bound it again.
    """

    code: str
    first: RuleDeclaration
    second: RuleDeclaration

    def __init__(self, code: str, first: RuleDeclaration, second: RuleDeclaration) -> None:
        self.code = code
        self.first = first
        self.second = second
        super().__init__(f'alias code {code!r} of {second.__qualname__} is already bound to {first.__qualname__}')


class Registry:
    """The rules a rules package declares, in code order, found by their code, their name or an alias code.

    Codes, names and alias codes share one namespace, so a lookup by any of them finds one declaration at most.
    """

    _rules: tuple[RuleDeclaration, ...]
    _by_key: dict[str, RuleDeclaration]

    def __init__(self, declarations: Iterable[RuleDeclaration]) -> None:
        """Index the declarations, rejecting any the registry cannot hold.

        Codes are bound first, then names, then alias codes, so a clash between two kinds is reported as the
        later kind's error.

        Args:
            declarations: The rules to hold, in any order.

        Raises:
            DuplicateRuleCodeError: If a code is bound twice.
            DuplicateRuleNameError: If a name is bound twice, or is already bound as a code.
            DuplicateAliasCodeError: If an alias code is bound twice, or is already bound as a code or a name.
        """
        rule_classes, removed_rules = _split_by_kind(declarations)

        self._rules = tuple(sorted((*rule_classes, *removed_rules), key=_printed_code))
        self._by_key = {}

        for declaration in self._rules:
            code = str(declaration.CODE)
            first = self._by_key.get(code)
            if first is not None:
                raise DuplicateRuleCodeError(code, first, declaration)
            self._by_key[code] = declaration

        for declaration in self._rules:
            first = self._by_key.get(declaration.NAME)
            if first is not None:
                raise DuplicateRuleNameError(declaration.NAME, first, declaration)
            self._by_key[declaration.NAME] = declaration

        for rule_class in sorted(rule_classes, key=_printed_code):
            for alias in rule_class.ALIASES:
                code = str(alias)
                first = self._by_key.get(code)
                if first is not None:
                    raise DuplicateAliasCodeError(code, first, rule_class)
                self._by_key[code] = rule_class

    @classmethod
    def load(cls, package: ModuleType) -> Self:
        """Import every module of a rules package but its unit tests, and hold the rules declared in it.

        Args:
            package: The rules package, walked with its subpackages.

        Raises:
            DuplicateRuleCodeError: If a code is bound twice.
            DuplicateRuleNameError: If a name is bound twice, or is already bound as a code.
            DuplicateAliasCodeError: If an alias code is bound twice, or is already bound as a code or a name.
            Exception: Whatever a module of the package raises as it is imported, unchanged, since a registry
                missing a module's rules would check less than the package declares.
        """
        _import_modules(package)
        return cls(
            declaration
            for declaration in declared_rules()
            if _is_in_package(declaration.__module__, package.__name__)
            and not _is_in_unit_tests(declaration.__module__, package.__name__)
        )

    @property
    def rules(self) -> tuple[RuleDeclaration, ...]:
        """Every rule held, in code order, as the code prints."""
        return self._rules

    def find(self, key: str) -> RuleDeclaration | None:
        """The rule with this code, name or alias code, or None when no rule has it.

        Args:
            key: A code as printed, such as `OUT002`, a name, such as `empty-section`, or an alias code, such as
                `MD040`.
        """
        return self._by_key.get(key)


@cache
def package_registry() -> Registry:
    """The registry of the rules the package ships, from `lorecraft.rules`, its unit tests left out.

    Built on the first call and kept for the life of the process: the rules are package data, fixed for as long
    as the process runs.

    Raises:
        DuplicateRuleCodeError: If a code is bound twice.
        DuplicateRuleNameError: If a name is bound twice, or is already bound as a code.
        DuplicateAliasCodeError: If an alias code is bound twice, or is already bound as a code or a name.
        Exception: Whatever a rule module raises as it is imported, unchanged.
    """
    return Registry.load(rules)


def _import_modules(package: ModuleType) -> None:
    """Import every module of a package, descending into each subpackage but its unit tests.

    Args:
        package: The package to walk; it is already imported.

    Raises:
        Exception: Whatever a module raises as it is imported, unchanged.
    """
    for module_info in pkgutil.iter_modules(package.__path__):
        # `lorecraft.rules` holds its own unit tests, whose sample rules reuse codes and include a module that fails
        # to import, so the walk of the package's own rules never enters a subpackage of tests.
        if module_info.ispkg and module_info.name == _UNIT_TESTS:
            continue
        module = importlib.import_module(f'{package.__name__}.{module_info.name}')
        if module_info.ispkg:
            _import_modules(module)


def _is_in_package(module_name: str, package_name: str) -> bool:
    """Whether the module named `module_name` is the package named `package_name` or lies beneath it.

    Args:
        module_name: The dotted name of the module a declaration was made in.
        package_name: The dotted name of the rules package.
    """
    return module_name == package_name or module_name.startswith(f'{package_name}.')


def _is_in_unit_tests(module_name: str, package_name: str) -> bool:
    """Whether the module named `module_name` lies in a subpackage of unit tests beneath the package `package_name`.

    The walk never imports such a module, but a test may already have, and `@rule` recorded the sample rules it
    declares beside the package's own; so the registry leaves them out by their module's name as well.

    Args:
        module_name: The dotted name of the module a declaration was made in.
        package_name: The dotted name of the rules package.
    """
    if not module_name.startswith(f'{package_name}.'):
        return False
    path_beneath_package = module_name.removeprefix(f'{package_name}.').split('.')
    return _UNIT_TESTS in path_beneath_package


def _split_by_kind(
    declarations: Iterable[RuleDeclaration],
) -> tuple[tuple[type[Rule], ...], tuple[type[RemovedRule], ...]]:
    """Separate the rules in service from the removed rules, each in the order given.

    A `match` class pattern tests an instance, not a class, so the branch on a declaration's kind is an
    `issubclass` chain, closed by `assert_never` so a third kind of declaration is a type error here.

    Args:
        declarations: The rules to separate.
    """
    rule_classes: list[type[Rule]] = []
    removed_rules: list[type[RemovedRule]] = []
    for declaration in declarations:
        if issubclass(declaration, Rule):
            rule_classes.append(declaration)
        elif issubclass(declaration, RemovedRule):
            removed_rules.append(declaration)
        else:
            assert_never(declaration)
    return tuple(rule_classes), tuple(removed_rules)


def _printed_code(declaration: RuleDeclaration) -> str:
    """The declaration's code as output prints it, the key that orders the registry."""
    return str(declaration.CODE)
