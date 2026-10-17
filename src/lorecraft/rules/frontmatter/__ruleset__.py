"""What the `FM` group's rules share: the group, and under which meta spec an occurrence is reported.

A document's frontmatter block is governed by the structure file of its corpus, and a skill's by the
package, after the Agent Skills specification, which no file in the repository holds. Rules over both subject kinds
derive from `FrontmatterRule`, so one check judges a document and a skill alike, and reads which of the two governs the
subject from its context, through `owner_spec` for the block and `schema_spec` for a schema's problems. It says which
it is through `spec_note` or `schema_note`, so a document's occurrence and a skill's read apart. Rules over a skill's
`allowed-tools` alone derive from `SkillRule`, and both say where the meta spec states the field through
`ALLOWED_TOOLS_NOTE`; its recommended length is set by Lorecraft, not the meta spec.

A field's line, or line 1 in its absence, is decided in one place, `field_line` in `lorecraft.project.schemas`: the
schema problems arrive placed through it, and a rule that reports at a field's line calls it rather than search the
keys itself.

What the schema states about a field reaches the reader as typed data on the occurrence, rendered the same way by every
rule that has it: the values it allows through `allowed_values_help`, an example through `example_note`. A rule lists
its children in one order: the note naming the meta spec first, then the help, then the other notes.
"""

from typing import Final, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import (
    AgentSkillsSchema,
    DocumentFrontmatterOwner,
    FrontmatterOwner,
    SchemaSource,
    SkillFrontmatterOwner,
    StructureSpecSchema,
)
from lorecraft.rules.identity import RuleGroup, RuleGroupPrefix
from lorecraft.rules.location import Elsewhere, Help, Note

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('FM'), 'Frontmatter checks')
"""The group of the rules over a subject's frontmatter: the block itself, and the schema that governs it."""


def owner_spec(owner: FrontmatterOwner) -> RootRelativePath | None:
    """The structure file that states the group's rules for this subject, or `None` for a skill.

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


def spec_note(owner: FrontmatterOwner) -> Note:
    """The note naming the meta spec that governs the subject's frontmatter.

    Args:
        owner: The document or the skill whose frontmatter is judged.
    """
    match owner:
        case DocumentFrontmatterOwner():
            return Note('the frontmatter schema is set here', at=Elsewhere(owner.spec))
        case SkillFrontmatterOwner():
            return Note("the Agent Skills specification governs a SKILL.md's frontmatter")
        case _:
            assert_never(owner)


def schema_spec(source: SchemaSource) -> RootRelativePath | None:
    """The structure file that states a frontmatter schema, or `None` for the Agent Skills specification's.

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


def schema_note(source: SchemaSource) -> Note:
    """The note naming where the frontmatter schema that found a problem is stated.

    Args:
        source: The schema the problem was found against.
    """
    match source:
        case StructureSpecSchema():
            return Note('the frontmatter schema is set here', at=Elsewhere(source.spec))
        case AgentSkillsSchema():
            return Note("the Agent Skills specification states a SKILL.md's frontmatter schema")
        case _:
            assert_never(source)


def allowed_values_help(values: tuple[str, ...]) -> Help:
    """The help naming the values a field is restricted to.

    Args:
        values: The values the schema allows, each as text; there is at least one.
    """
    if len(values) == 1:
        return Help(f'write {values[0]}')
    return Help(f'write one of: {", ".join(values)}')


def example_note(field: str, example: str) -> Note:
    """The note showing the example a schema gives for a field, as it wrote it.

    The example is a sample of the field to write, so it takes lines of its own, as an outline entry's example does.

    Args:
        field: The field the example is for.
        example: The example, as text.
    """
    return Note(f'for example:\n{field}: {example}')


ALLOWED_TOOLS_NOTE: Final[Note] = Note(
    "the Agent Skills specification's experimental `allowed-tools` field: "
    'https://agentskills.io/specification#allowed-tools-field'
)
"""The note naming where the Agent Skills specification states `allowed-tools`, which it marks experimental."""
