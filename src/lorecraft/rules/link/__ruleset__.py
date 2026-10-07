"""What the `LINK` group's rules share: the group they are declared under."""

from typing import Final

from lorecraft.rules.declaration import RuleGroup, RuleGroupPrefix

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('LINK'), 'Links in Markdown files')
"""The group of the rules over the links and images of a Markdown file: a document, a skill's `SKILL.md` or one of
its resources."""
