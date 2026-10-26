"""What the `LC5xx` group's rules share: the group, and the note naming the spec that reads a skill's links.

A relative link in a skill's file is read from the skill root, not from the file's own directory, as the Agent Skills
spec has it. The Agent Skills specification is no file in the repository: the package states it. The rules
that depend on it, the ones over where a link leads, say so through `SKILL_NOTE`.
"""

from typing import Final, Protocol

from lorecraft.project.query import GovernancePrimitives, LinkResolutionPrimitives, SyntaxPrimitives
from lorecraft.rules.identity import RuleGroup, RuleGroupPrefix
from lorecraft.rules.location import Note

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('LC'), 'Links in Markdown files', range(500, 508))
"""The group of the rules over the links and images of a Markdown file: a document, a skill's `SKILL.md` or one of
its resources."""


SKILL_NOTE: Final[Note] = Note("the Agent Skills specification reads a skill's relative links from the skill root")
"""The note naming the spec that has a skill's relative links read from the skill root."""


class SyntaxLinkResolutionPrimitives(SyntaxPrimitives, LinkResolutionPrimitives, Protocol):
    """The primitives the queries over a file's links and where they lead read."""


class GovernanceSyntaxLinkResolutionPrimitives(
    GovernancePrimitives, SyntaxPrimitives, LinkResolutionPrimitives, Protocol
):
    """The primitives the queries over a document's links and where they lead read."""
