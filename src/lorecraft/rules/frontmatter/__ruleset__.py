"""What the `FM` group's rules share: the group, and where and under which specification an occurrence is reported.

A document's frontmatter block is governed by the structure specification of its corpus, and a skill's by the
package, after the Agent Skills specification, which no file in the repository holds. Every rule of the group reads
the subject's kind from its input, through `owner_spec`, and says which of the two states it through `spec_note`, so
a document's occurrence and a skill's read apart.

A rule never locates a line of the frontmatter itself: the builders of the group's inputs, in `lorecraft.checks`,
locate each field through `field_line`, the one place a field's line, or line 1 in its absence, is decided.
"""

from typing import Final, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import Frontmatter, LineNumber
from lorecraft.rules.declaration import RuleGroup
from lorecraft.rules.inputs import DocumentFrontmatterOwner, FrontmatterOwner, SkillFrontmatterOwner
from lorecraft.rules.location import Elsewhere, Note

GROUP_ID: Final[RuleGroup] = RuleGroup('FM', 'Frontmatter checks')
"""The group of the rules over a subject's frontmatter: the block itself, and the schema that governs it."""

FIRST_LINE: Final[LineNumber] = LineNumber.from_int(1)
"""Where an occurrence with no more precise line is reported: the subject's first line, which opens the block."""


def owner_spec(owner: FrontmatterOwner) -> RootRelativePath | None:
    """The specification file that states the group's rules for this subject, or `None` for a skill.

    Args:
        owner: The document or the skill whose frontmatter is judged.
    """
    match owner:
        case DocumentFrontmatterOwner():
            return owner.spec
        case SkillFrontmatterOwner():
            # The Agent Skills specification is no file in the repository: the package states it.
            return None
        case _:
            assert_never(owner)


def spec_note(spec: RootRelativePath | None) -> Note:
    """The note naming the specification that governs the subject's frontmatter.

    Args:
        spec: The structure specification whose frontmatter schema governs a document, or `None` for a skill, which
            the Agent Skills specification governs.
    """
    if spec is None:
        return Note("the Agent Skills specification governs a SKILL.md's frontmatter")
    return Note('the frontmatter schema is set here', at=Elsewhere(spec))


def field_line(frontmatter: Frontmatter, field: str) -> LineNumber:
    """The line a top-level field is written on, or line 1 when the mapping does not write it.

    A field only a `<<` merge supplies is not written by the mapping, so it is reported on line 1.

    Args:
        frontmatter: The decoded frontmatter, whose top-level keys carry the line each is written on.
        field: Name of the top-level key to find.
    """
    line = frontmatter.find_key_line(field)
    if line is None:
        return FIRST_LINE
    return line
