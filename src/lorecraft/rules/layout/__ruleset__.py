"""What the `LC1xx` group's rules share: the group they are declared under."""

from typing import Final

from lorecraft.rules.identity import RuleGroup, RuleGroupPrefix

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('LC'), 'Workspace checks', range(100, 200))
"""The group of the rules over the skill layout: the skills directories, the entries in them and the files of each
skill, as an agent lists and follows them."""
