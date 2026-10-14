"""A sample removed rule declared with a code in the engine's group."""

from typing import ClassVar

from lorecraft.rules.collector import rule
from lorecraft.rules.declaration import RemovedRule, RuleCode
from lorecraft.rules.engine.__ruleset__ import GROUP_ID
from lorecraft.rules.identity import Release, RuleName


@rule
class RetiredTrespasser(RemovedRule):
    """A sample removed rule whose code is in the group reserved for engine conditions."""

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 902)
    NAME: ClassVar[RuleName] = RuleName('retired-trespasser')
    REMOVED_IN: ClassVar[Release] = Release('1.1.0')
    REPLACED_BY: ClassVar[RuleCode | None] = None
