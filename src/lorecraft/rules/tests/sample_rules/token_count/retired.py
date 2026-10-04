"""A sample removed rule, replaced by `over-half-budget`."""

from typing import ClassVar

from lorecraft.rules.declaration import Release, RemovedRule, RuleCode, RuleName, rule

from ..groups import SAMPLE


@rule
class NearBudget(RemovedRule):
    """A document came near its budget; retired for `over-half-budget`, which says how near."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 4)
    NAME: ClassVar[RuleName] = RuleName('near-budget')
    REMOVED_IN: ClassVar[Release] = Release('1.1.0')
    REPLACED_BY: ClassVar[RuleCode | None] = RuleCode(SAMPLE, 1)
