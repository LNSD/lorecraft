"""What the `FM` group's rules share: the group, and under which specification an occurrence is reported.

A document's frontmatter block is governed by the structure specification of its corpus, and a skill's by the
package, after the Agent Skills specification, which no file in the repository holds. Every rule of the group reads
which of the two governs the subject from its input, through `owner_spec` for the block and `schema_spec` for a
schema's problems, and says which it is through `spec_note` or `schema_note`, so a document's occurrence and a
skill's read apart.

A rule never locates a line of the frontmatter itself: its input arrives with each line located, through
`field_line` in `lorecraft.project.schemas`, the one place a field's line, or line 1 in its absence, is decided.
"""

from typing import Final, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import DocumentFrontmatterOwner, FrontmatterOwner, SkillFrontmatterOwner
from lorecraft.project.schemas import AgentSkillsSchema, SchemaSource, StructureSpecSchema
from lorecraft.rules.declaration import RuleGroup
from lorecraft.rules.location import Elsewhere, Note

GROUP_ID: Final[RuleGroup] = RuleGroup('FM', 'Frontmatter checks')
"""The group of the rules over a subject's frontmatter: the block itself, and the schema that governs it."""


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


def schema_spec(source: SchemaSource) -> RootRelativePath | None:
    """The specification file that states a frontmatter schema, or `None` for the Agent Skills specification's.

    Args:
        source: The schema a set of problems was found against.
    """
    match source:
        case StructureSpecSchema():
            return source.spec
        case AgentSkillsSchema():
            # The Agent Skills specification is no file in the repository: the package states it.
            return None
        case _:
            assert_never(source)


def schema_note(spec: RootRelativePath | None) -> Note:
    """The note naming where the frontmatter schema that found a problem is stated.

    Args:
        spec: The structure specification that states the schema, or `None` for the Agent Skills specification's.
    """
    if spec is None:
        return Note("the Agent Skills specification states a SKILL.md's frontmatter schema")
    return Note('the frontmatter schema is set here', at=Elsewhere(spec))
