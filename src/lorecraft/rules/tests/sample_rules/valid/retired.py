"""A sample removed rule, replaced by `trailing-space`."""

from typing import ClassVar

from lorecraft.rules.collector import rule
from lorecraft.rules.declaration import RemovedRule, Rule
from lorecraft.rules.identity import Release, RuleCode, RuleName

from ..groups import SAMPLE
from .trailing_space import TrailingSpace


@rule
class TabIndent(RemovedRule):
    """A line was indented with a tab; retired for `trailing-space`, which the samples needed more."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 3)
    NAME: ClassVar[RuleName] = RuleName('tab-indent')
    REMOVED_IN: ClassVar[Release] = Release('1.3.0')
    REPLACED_BY: ClassVar[type[Rule] | None] = TrailingSpace
