"""What the `LC1xx` group's rules share: the group they are declared under."""

from typing import Final

from lorecraft.rules.identity import RuleGroup, RuleGroupPrefix

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('LC'), 'Workspace checks', range(100, 200))
"""The group of the rules over the directories directly under `docs/`, as a corpus names them."""
