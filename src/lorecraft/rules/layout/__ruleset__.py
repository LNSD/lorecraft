"""What the `LAY` group's rules share: the group they are declared under."""

from typing import Final

from lorecraft.rules.declaration import RuleGroup

GROUP_ID: Final[RuleGroup] = RuleGroup('LAY', 'Skill layout checks')
"""The group of the rules over the skill layout: the skills directories, the entries in them and the files of each
skill, as an agent lists and follows them."""
