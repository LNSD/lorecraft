"""A sample removed rule that does not say what replaced it."""

from typing import ClassVar

from lorecraft.rules.rule import Release, RemovedRule, RuleCode, RuleName, rule

from ..groups import SAMPLE


@rule
class Unreplaced(RemovedRule):
    """A sample removed rule that leaves `REPLACED_BY` unbound, rather than None."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[RuleName] = RuleName('unreplaced')
    REMOVED_IN: ClassVar[Release] = Release('1.1.0')
