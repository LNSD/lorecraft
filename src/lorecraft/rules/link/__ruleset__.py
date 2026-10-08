"""What the `LINK` group's rules share: the group, and the note naming the specification that reads a skill's links.

A relative link in a skill's file is read from the skill root, not from the file's own directory, as the Agent Skills
specification has it. The Agent Skills specification is no file in the repository: the package states it. The rules
that depend on it, the ones over where a link leads, say so through `skill_note`.
"""

from typing import Final

from lorecraft.rules.declaration import RuleGroup, RuleGroupPrefix
from lorecraft.rules.location import Note

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('LINK'), 'Links in Markdown files')
"""The group of the rules over the links and images of a Markdown file: a document, a skill's `SKILL.md` or one of
its resources."""


def skill_note() -> Note:
    """The note naming the specification that has a skill's relative links read from the skill root."""
    return Note("the Agent Skills specification reads a skill's relative links from the skill root")
