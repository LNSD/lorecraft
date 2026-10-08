"""The one list of rules: every declaration `@rule` registered in a rules package, in code order.

A rule joins the registry by being declared with `@rule` in a module of `lorecraft.rules`; nothing lists the
rules anywhere else. `Registry.load` imports every module of a package, its subpackages included and its unit
tests left out, and keeps the declarations whose module lies in that package outside its unit tests, so a test
that walks a package of sample rules sees only those, and the package's own registry never sees them.

The registry is package data: it reads no workspace and is not a query. A rejection, a code, a name or an alias
code bound twice, a removed rule replaced by a code no rule declares, a prefix given two groups, a class attribute
left unbound, a rule over a document that declares no facet among them, a rule or a condition still abstract, or a
code in a group its kind may not use, is a defect in `lorecraft.rules`, never in the user's repository, so it raises
a `RuntimeError` whose traceback locates the declaration.

A command's composition root builds the registry with `Registry.load(rules)`, once per invocation, and hands it to
what reads it; nothing below the composition root imports a registry or keeps one. A long-lived process builds it
once as it starts and keeps it for its lifetime, since the rules are fixed for as long as the process runs.

The engine's group is reserved for engine conditions, and every condition is in it. No type can say which group a
code is in, so the registry holds both directions as it loads.
"""

import importlib
import inspect
import pkgutil
from collections.abc import Iterable
from types import ModuleType
from typing import Final, Self, assert_never

from .declaration import (
    EngineCondition,
    RemovedRule,
    Rule,
    RuleDeclaration,
    RuleGroup,
    RuleGroupPrefix,
    RuleName,
    declared_rules,
)
from .engine.__ruleset__ import GROUP_ID as ENGINE_GROUP_ID
from .subject import DocumentRule

_UNIT_TESTS: Final[str] = 'tests'
"""The name of the subpackage beside a package's modules that holds their unit tests, fixed by the unit tier."""

_RULE_ATTRIBUTES: Final[tuple[str, ...]] = ('CODE', 'NAME', 'LEVEL', 'SINCE')
"""The class attributes a rule's class must bind; `ALIASES` has a default, so it is not among them."""

_DOCUMENT_RULE_ATTRIBUTES: Final[tuple[str, ...]] = ('GOVERNED_BY',)
"""The class attributes a rule over a document must bind besides a rule's: the facet it reads."""

_REMOVED_RULE_ATTRIBUTES: Final[tuple[str, ...]] = ('CODE', 'NAME', 'REMOVED_IN', 'REPLACED_BY')
"""The class attributes a removed rule must bind; `REPLACED_BY` is bound to None when nothing replaced it."""

_CONDITION_ATTRIBUTES: Final[tuple[str, ...]] = ('CODE', 'NAME', 'SINCE', 'SEVERITY')
"""The class attributes an engine condition must bind."""


class UnsetRuleAttributeError(RuntimeError):
    """A declaration leaves a class attribute its kind requires unbound, such as a rule with no `SINCE`.

    The base classes only annotate these attributes, so the type checker accepts a subclass that never binds one.

    Attributes:
        declaration: The declaration missing the attribute.
        attribute: The name of the unbound attribute.
    """

    declaration: RuleDeclaration
    attribute: str

    def __init__(self, declaration: RuleDeclaration, attribute: str) -> None:
        self.declaration = declaration
        self.attribute = attribute
        super().__init__(f'declaration {declaration.__qualname__} does not bind {attribute}')


class ConflictingRuleGroupError(RuntimeError):
    """Two declarations give one prefix two different groups, so the prefix has no single title.

    Attributes:
        prefix: The prefix declared twice.
        first: The declaration whose group bound the prefix first.
        second: The declaration whose group differs from it.
    """

    prefix: RuleGroupPrefix
    first: RuleDeclaration
    second: RuleDeclaration

    def __init__(self, prefix: RuleGroupPrefix, first: RuleDeclaration, second: RuleDeclaration) -> None:
        self.prefix = prefix
        self.first = first
        self.second = second
        super().__init__(
            f'rule group {str(prefix)!r} of {second.__qualname__} is titled {second.CODE.group.title!r}, but '
            f'{first.__qualname__} titles it {first.CODE.group.title!r}'
        )


class DuplicateRuleCodeError(RuntimeError):
    """Two declarations share a code, whichever their kinds: rules, removed rules or engine conditions.

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


class UnknownReplacementError(RuntimeError):
    """A removed rule names, as the rule that replaced it, a code that no declaration holds.

    Attributes:
        removed_rule: The removed rule.
    """

    removed_rule: type[RemovedRule]

    def __init__(self, removed_rule: type[RemovedRule]) -> None:
        self.removed_rule = removed_rule
        super().__init__(
            f'removed rule {removed_rule.__qualname__} is replaced by {removed_rule.REPLACED_BY}, '
            'which no rule declares'
        )


class DuplicateRuleNameError(RuntimeError):
    """Two declarations share a name.

    A name is never spelled as a code: a name is lowercase, and a code starts with its uppercase prefix.

    Attributes:
        name: The name bound twice.
        first: The declaration the name was bound to first.
        second: The declaration that bound it again.
    """

    name: RuleName
    first: RuleDeclaration
    second: RuleDeclaration

    def __init__(self, name: RuleName, first: RuleDeclaration, second: RuleDeclaration) -> None:
        self.name = name
        self.first = first
        self.second = second
        super().__init__(f'rule name {str(name)!r} of {second.__qualname__} is already bound to {first.__qualname__}')


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


class AbstractRuleError(RuntimeError):
    """A rule's class or an engine condition is still abstract, such as a rule with no `check`, so it is never built.

    Attributes:
        declaration: The abstract rule class or engine condition.
        missing: The names of the methods it leaves abstract, in name order.
    """

    declaration: type[Rule] | type[EngineCondition]
    missing: tuple[str, ...]

    def __init__(self, declaration: type[Rule] | type[EngineCondition], missing: tuple[str, ...]) -> None:
        self.declaration = declaration
        self.missing = missing
        super().__init__(
            f'declaration {declaration.__qualname__} is abstract: it does not implement {", ".join(missing)}'
        )


class ConditionOutsideEngineGroupError(RuntimeError):
    """An engine condition's code is outside the engine's group, which every condition's code is in.

    Attributes:
        declaration: The engine condition.
    """

    declaration: type[EngineCondition]

    def __init__(self, declaration: type[EngineCondition]) -> None:
        self.declaration = declaration
        group = declaration.CODE.group
        super().__init__(
            f'engine condition {declaration.__qualname__} has the code {str(declaration.CODE)!r}, in the group '
            f'{str(group.prefix)!r} titled {group.title!r}, not the engine group '
            f'{str(ENGINE_GROUP_ID.prefix)!r} titled {ENGINE_GROUP_ID.title!r}'
        )


class RuleInEngineGroupError(RuntimeError):
    """A rule or a removed rule has its code in the engine's group, which is reserved for engine conditions.

    Attributes:
        declaration: The rule class or removed rule.
    """

    declaration: type[Rule] | type[RemovedRule]

    def __init__(self, declaration: type[Rule] | type[RemovedRule]) -> None:
        self.declaration = declaration
        super().__init__(
            f'rule {declaration.__qualname__} has the code {str(declaration.CODE)!r}, in the engine group '
            f'{str(ENGINE_GROUP_ID.prefix)!r} reserved for engine conditions'
        )


class Registry:
    """The rules a rules package declares, in code order, found by their code, their name or an alias code.

    Codes, names and alias codes share one namespace, so a lookup by any of them finds one declaration at most. A
    group is found apart, by its prefix.
    """

    _rules: tuple[RuleDeclaration, ...]
    _rules_in_service: tuple[type[Rule], ...]
    _by_key: dict[str, RuleDeclaration]
    _groups: dict[str, RuleGroup]

    def __init__(self, declarations: Iterable[RuleDeclaration]) -> None:
        """Index the declarations, rejecting any the registry cannot hold.

        Codes are bound first, then names, then alias codes, so a clash between two kinds is reported as the
        later kind's error.

        Args:
            declarations: The rules to hold, in any order.

        Raises:
            UnsetRuleAttributeError: If a declaration leaves a class attribute its kind requires unbound, the facet
                of a rule over a document among them.
            AbstractRuleError: If a rule class or an engine condition is still abstract.
            RuleInEngineGroupError: If a rule's or a removed rule's code is in the engine's group.
            ConditionOutsideEngineGroupError: If an engine condition's code is outside the engine's group.
            DuplicateRuleCodeError: If a code is bound twice.
            UnknownReplacementError: If a removed rule is replaced by a code no declaration holds.
            ConflictingRuleGroupError: If two codes give one prefix two different groups.
            DuplicateRuleNameError: If a name is bound twice.
            DuplicateAliasCodeError: If an alias code is bound twice, or is already bound as a code or a name.
        """
        rule_classes, removed_rules, conditions = _split_by_kind(declarations)

        for rule_class in rule_classes:
            _require_attributes(rule_class, _RULE_ATTRIBUTES)
        # The runner gates a rule over a document on the facet it declares, so one that declares none would never run.
        for rule_class in rule_classes:
            if issubclass(rule_class, DocumentRule):
                _require_attributes(rule_class, _DOCUMENT_RULE_ATTRIBUTES)
        for removed_rule in removed_rules:
            _require_attributes(removed_rule, _REMOVED_RULE_ATTRIBUTES)
        for condition in conditions:
            _require_attributes(condition, _CONDITION_ATTRIBUTES)

        for rule_class in rule_classes:
            if inspect.isabstract(rule_class):
                missing = tuple(sorted(rule_class.__abstractmethods__))
                raise AbstractRuleError(rule_class, missing)
        for condition in conditions:
            if inspect.isabstract(condition):
                missing = tuple(sorted(condition.__abstractmethods__))
                raise AbstractRuleError(condition, missing)

        # A rule is compared by prefix rather than by group, so one that retitles `LC` is refused as well.
        for rule_class in rule_classes:
            if rule_class.CODE.group.prefix == ENGINE_GROUP_ID.prefix:
                raise RuleInEngineGroupError(rule_class)
        for removed_rule in removed_rules:
            if removed_rule.CODE.group.prefix == ENGINE_GROUP_ID.prefix:
                raise RuleInEngineGroupError(removed_rule)
        for condition in conditions:
            if condition.CODE.group != ENGINE_GROUP_ID:
                raise ConditionOutsideEngineGroupError(condition)

        self._rules = tuple(sorted((*rule_classes, *removed_rules, *conditions), key=_printed_code))
        self._rules_in_service = tuple(sorted(rule_classes, key=_printed_code))
        self._by_key = {}
        self._groups = {}

        groups: dict[RuleGroupPrefix, tuple[RuleGroup, RuleDeclaration]] = {}
        for declaration in self._rules:
            code = str(declaration.CODE)
            first = self._by_key.get(code)
            if first is not None:
                raise DuplicateRuleCodeError(code, first, declaration)
            self._by_key[code] = declaration

            group = declaration.CODE.group
            bound = groups.get(group.prefix)
            if bound is None:
                groups[group.prefix] = (group, declaration)
            elif bound[0] != group:
                raise ConflictingRuleGroupError(group.prefix, bound[1], declaration)

        # Every code is bound, so a replacement is checked against all of them, whichever order the rules sit in.
        for removed_rule in removed_rules:
            replaced_by = removed_rule.REPLACED_BY
            if replaced_by is not None and str(replaced_by) not in self._by_key:
                raise UnknownReplacementError(removed_rule)

        # A group whose every code is a removed rule holds nothing a run could select, so it is not found by its prefix.
        # Keyed by the prefix as text: `find_group` looks up what a user typed, which need not be a valid prefix.
        for declaration in (*rule_classes, *conditions):
            self._groups[str(declaration.CODE.group.prefix)] = declaration.CODE.group

        for declaration in self._rules:
            name = str(declaration.NAME)
            first = self._by_key.get(name)
            if first is not None:
                raise DuplicateRuleNameError(declaration.NAME, first, declaration)
            self._by_key[name] = declaration

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
            UnsetRuleAttributeError: If a declaration leaves a class attribute its kind requires unbound, the facet
                of a rule over a document among them.
            AbstractRuleError: If a rule class or an engine condition declared in the package is still abstract.
            RuleInEngineGroupError: If a rule's or a removed rule's code is in the engine's group.
            ConditionOutsideEngineGroupError: If an engine condition's code is outside the engine's group.
            DuplicateRuleCodeError: If a code is bound twice.
            UnknownReplacementError: If a removed rule is replaced by a code no declaration holds.
            ConflictingRuleGroupError: If two codes give one prefix two different groups.
            DuplicateRuleNameError: If a name is bound twice.
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

    @property
    def rules_in_service(self) -> tuple[type[Rule], ...]:
        """The rules a run may enable, in code order: every rule held but the removed rules and engine conditions."""
        return self._rules_in_service

    def find(self, key: str) -> RuleDeclaration | None:
        """The rule with this code, name or alias code, or None when no rule has it.

        Args:
            key: A code as printed, such as `OUT002`, a name, such as `empty-section`, or an alias code, such as
                `MD040`.
        """
        return self._by_key.get(key)

    def find_group(self, prefix: str) -> RuleGroup | None:
        """The group with this prefix, or None when no rule in service nor engine condition held is in a group with it.

        The prefix is looked up as text, as `find` looks up a code, so text no prefix could be, such as `out`, is not
        an error: no group has it.

        Args:
            prefix: A group's prefix as spelled, such as `OUT`.
        """
        return self._groups.get(prefix)

    def is_engine_group(self, group: RuleGroup) -> bool:
        """Whether a group is the engine's, reserved for engine conditions, which every run reports.

        Args:
            group: A group the registry found, such as by `find_group`.
        """
        return group.prefix == ENGINE_GROUP_ID.prefix


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
) -> tuple[tuple[type[Rule], ...], tuple[type[RemovedRule], ...], tuple[type[EngineCondition], ...]]:
    """Separate the rules in service, the removed rules and the engine conditions, each in the order given.

    A `match` class pattern tests an instance, not a class, so the branch on a declaration's kind is an
    `issubclass` chain, closed by `assert_never` so a fourth kind of declaration is a type error here.

    Args:
        declarations: The rules to separate.
    """
    rule_classes: list[type[Rule]] = []
    removed_rules: list[type[RemovedRule]] = []
    conditions: list[type[EngineCondition]] = []
    for declaration in declarations:
        if issubclass(declaration, Rule):
            rule_classes.append(declaration)
        elif issubclass(declaration, RemovedRule):
            removed_rules.append(declaration)
        elif issubclass(declaration, EngineCondition):
            conditions.append(declaration)
        else:
            assert_never(declaration)
    return tuple(rule_classes), tuple(removed_rules), tuple(conditions)


def _require_attributes(declaration: RuleDeclaration, attributes: tuple[str, ...]) -> None:
    """Reject a declaration that leaves one of its kind's class attributes unbound.

    Args:
        declaration: The rule, removed rule or engine condition to inspect.
        attributes: The names its kind requires it to bind.

    Raises:
        UnsetRuleAttributeError: If one of the attributes is unbound, naming the first in the given order.
    """
    for attribute in attributes:
        if not hasattr(declaration, attribute):
            raise UnsetRuleAttributeError(declaration, attribute)


def _printed_code(declaration: RuleDeclaration) -> str:
    """The declaration's code as output prints it, the key that orders the registry."""
    return str(declaration.CODE)
