"""What the `LC2xx` group's rules share: the group and the schemas governing each subject's frontmatter.

A document's and a skill's frontmatter block is governed by the ordered schema inputs available to it. Rules over
both subject kinds declare a gate for each and judge either kind through the shared query facts. The frontmatter
part is governed when at least one applicable schema is loaded. `owner_spec` and `schema_spec` state which spec
grounds an occurrence, and `spec_note` or `schema_note` says which it is. Rules over a skill's `allowed-tools` use
`Always` and name the field's source through `ALLOWED_TOOLS_NOTE`; its recommended length is set by Lorecraft, not
the spec.

A field's line, or line 1 in its absence, is decided in one place, `field_line` in `lorecraft.project.schemas`: the
schema problems arrive placed through it, and a rule that reports at a field's line calls it rather than search the
keys itself.

What the schema states about a field reaches the reader as typed data on the occurrence, rendered the same way by every
rule that has it: the values it allows through `allowed_values_help`, an example through `example_note`. A rule lists
its children in one order: the note naming the spec first, then the help, then the other notes.
"""

from dataclasses import dataclass
from typing import Final, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.query import ItemPrimitives, item_frontmatter
from lorecraft.project.schemas import (
    AllowedTools,
    DocumentFrontmatterOwner,
    FrontmatterOwner,
    SkillField,
    SkillFrontmatterOwner,
    field_line,
    owner_of_frontmatter,
    parsed_skill_fields,
)
from lorecraft.project.syntax import Frontmatter, FrontmatterNode, LineNumber
from lorecraft.rules.identity import RuleGroup, RuleGroupPrefix
from lorecraft.rules.location import Elsewhere, Note

GROUP_ID: Final[RuleGroup] = RuleGroup(RuleGroupPrefix('LC'), 'Frontmatter checks', range(200, 300))
"""The group of the rules over a subject's frontmatter: the block itself, and the schema that governs it."""


@dataclass(frozen=True, slots=True)
class FrontmatterFacts:
    """The frontmatter block a rule judges, and whose it is.

    Attributes:
        frontmatter: The block as parsed.
        owner: The document or the skill the block opens.
    """

    frontmatter: FrontmatterNode
    owner: FrontmatterOwner


def frontmatter_facts(primitives: ItemPrimitives) -> FrontmatterFacts:
    """The block and its owner, the facts the rules over the block itself share.

    Args:
        primitives: The model state of the document or the skill.
    """
    return FrontmatterFacts(primitives.query(item_frontmatter), primitives.query(owner_of_frontmatter))


@dataclass(frozen=True, slots=True)
class AllowedToolsField:
    """A skill's `allowed-tools` field as written, and the line it is written on.

    Attributes:
        line: The line of the field.
        tools: The field's value, split into entries.
    """

    line: LineNumber
    tools: AllowedTools


def allowed_tools_field(primitives: ItemPrimitives) -> AllowedToolsField | None:
    """The skill's `allowed-tools` field, the fact the two rules over it share; `None` when it holds no parsed value.

    Args:
        primitives: The model state of the skill.
    """
    frontmatter = primitives.query(item_frontmatter)
    if not isinstance(frontmatter, Frontmatter):
        return None
    tools = primitives.query(parsed_skill_fields).get(SkillField.ALLOWED_TOOLS)
    if not isinstance(tools, AllowedTools):
        return None
    return AllowedToolsField(field_line(frontmatter, SkillField.ALLOWED_TOOLS), tools)


def owner_spec(owner: FrontmatterOwner) -> RootRelativePath | None:
    """The base structure file that governs the subject's frontmatter, or `None` for a skill.

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
    """The note naming the spec that governs the subject's frontmatter.

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


ALLOWED_TOOLS_NOTE: Final[Note] = Note(
    "the Agent Skills specification's experimental `allowed-tools` field: "
    'https://agentskills.io/specification#allowed-tools-field'
)
"""The note naming where the Agent Skills specification states `allowed-tools`, which it marks experimental."""
