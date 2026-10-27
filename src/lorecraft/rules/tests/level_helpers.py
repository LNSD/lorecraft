"""Helpers for building rule default resolutions in tests."""

from ..declaration import Rule
from ..identity import EnabledLevel, Level


def default_level(rule: Rule | type[Rule]) -> EnabledLevel:
    """Return a narrowed rule default for constructing `DefaultLevel`.

    Args:
        rule: A rule class or occurrence used by a test.

    Raises:
        AssertionError: If the test tries to report an allow-level rule as a diagnostic.
    """
    rule_class = rule if isinstance(rule, type) else type(rule)
    match rule_class.LEVEL:
        case Level.ALLOW:
            raise AssertionError(f'allow-level rule {rule_class.CODE} has no reporting default')
        case Level.WARN | Level.DENY as level:
            return level
