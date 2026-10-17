"""The process-global collector of rule declarations: `@rule` records each as its module is imported."""

from .declaration import EntryCondition, FileCondition, RemovedRule, Rule, RuleDeclaration

# Every declaration `@rule` has seen in this process, in the order their modules were imported. A rules
# package's registry keeps those whose module lies in it.
_declared: list[RuleDeclaration] = []


# The type parameter only carries the decorated class's own type through, so a rule's name still names its class
# for the type checker; it ranges over no subject kind, and the registry takes none, as adr-009 states. Without the
# parameter, every decorated name would be retyped as `RuleDeclaration`, and a rule's own fields and `judge` would
# no longer type-check at its call sites.
def rule[T: Rule | RemovedRule | FileCondition | EntryCondition](declaration: type[T]) -> type[T]:
    """Register a rule's class, a removed rule or an engine condition, as its module is imported.

    Args:
        declaration: The class that declares the rule.

    Returns:
        The class unchanged.
    """
    _declared.append(declaration)
    return declaration


def declared_rules() -> tuple[RuleDeclaration, ...]:
    """Every declaration `@rule` has registered in this process, from every package, in the order seen."""
    return tuple(_declared)
