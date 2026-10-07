"""What the `LEN` group's rules share: the group they are declared under."""

from typing import Final

from lorecraft.rules.declaration import RuleGroup, RuleGroupPrefix

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('LEN'), 'Length limits')
"""The group of the rules that hold a subject to a length limit: a document's token budget among them."""
