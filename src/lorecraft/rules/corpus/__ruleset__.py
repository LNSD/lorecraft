"""What the `COR` group's rules share: the group they are declared under."""

from typing import Final

from lorecraft.rules.identity import RuleGroup, RuleGroupPrefix

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('COR'), 'Corpus directory checks')
"""The group of the rules over the directories directly under `docs/`, as a corpus names them."""
