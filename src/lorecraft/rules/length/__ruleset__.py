"""What the `LEN` group's rules share: the group they are declared under."""

from typing import Final

from lorecraft.rules.declaration import RuleGroup

GROUP_ID: Final[RuleGroup] = RuleGroup('LEN', 'Length limits')
"""The group of the rules that hold a subject to a length limit: a document's token budget among them."""
