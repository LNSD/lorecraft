"""Schema queries and diagnostic guidance shared by frontmatter rules."""

from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.query import ItemPrimitives
from lorecraft.project.schemas import (
    AgentSkillsSchema,
    SchemaProblems,
    SchemaSource,
    StructureSpecSchema,
    frontmatter_schema_problems,
)
from lorecraft.rules.location import Elsewhere, Help, Note


def schema_problems(primitives: ItemPrimitives) -> tuple[SchemaProblems, ...]:
    """What each schema that governs the subject rejects in its frontmatter, the fact the schema rules share.

    Args:
        primitives: The model state of the document or the skill.
    """
    return primitives.query(frontmatter_schema_problems)


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
