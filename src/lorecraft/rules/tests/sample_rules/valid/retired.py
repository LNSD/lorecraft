"""A sample removed rule, replaced by `trailing-space`."""

from typing import ClassVar

from lorecraft.rules.rule import Release, RemovedRule, RuleCode, RuleName, rule

from ..groups import SAMPLE


@rule
class TabIndent(RemovedRule):
    """A line was indented with a tab; retired for `trailing-space`, which the samples needed more."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 3)
    NAME: ClassVar[RuleName] = RuleName('tab-indent')
    REMOVED_IN: ClassVar[Release] = Release('1.3.0')
    REPLACED_BY: ClassVar[RuleCode | None] = RuleCode(SAMPLE, 2)
