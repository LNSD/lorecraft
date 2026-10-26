"""A sample removed rule whose replacement is a code that no rule declares."""

from typing import ClassVar

from lorecraft.rules.collector import rule
from lorecraft.rules.declaration import RemovedRule, Rule
from lorecraft.rules.identity import Release, RuleCode, RuleName
from lorecraft.rules.tests.sample_rules.valid.trailing_space import TrailingSpace

from ..groups import SAMPLE


@rule
class Orphaned(RemovedRule):
    """A sample removed rule replaced by `SMP002`, which the package does not declare."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[RuleName] = RuleName('orphaned')
    REMOVED_IN: ClassVar[Release] = Release('1.1.0')
    REPLACED_BY: ClassVar[type[Rule] | None] = TrailingSpace
