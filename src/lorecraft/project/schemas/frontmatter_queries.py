"""Facts of a frontmatter block, derived from raw syntax and governance primitives."""

from typing import TYPE_CHECKING

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import PathComponent
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.item import DocumentOrigin, SkillEntryOrigin, WrongItemKindError
from lorecraft.project.schemas.frontmatter_owner import (
    DocumentFrontmatterOwner,
    FrontmatterOwner,
    SkillFrontmatterOwner,
)
from lorecraft.project.schemas.schema_problems import (
    MissingFieldProblem,
    SchemaProblems,
    locate_schema_problems,
    locate_skill_schema_problems,
)
from lorecraft.project.schemas.skill_fields import SkillFields, parse_skill_fields

if TYPE_CHECKING:
    from lorecraft.project.query import Primitives


def frontmatter_owner_query(primitives: 'Primitives') -> FrontmatterOwner:
    """The document or skill whose frontmatter the item opens, from origin facts and governance.

    Raises:
        WrongItemKindError: If the item is not a skill entry or a document whose corpus states a structure spec.
    """
    origin = primitives.item_origin()
    match origin:
        case SkillEntryOrigin():
            return SkillFrontmatterOwner(
                directory_name=PathComponent.parse(origin.expected_name), link_target=origin.link_target
            )
        case DocumentOrigin():
            governance = primitives.item_governance()
            structure = governance.corpus_structure() if governance is not None else None
            if structure is None:
                raise WrongItemKindError('a document whose corpus states a structure specification')
            return DocumentFrontmatterOwner(filename=AspectFilename.parse(origin.expected_name), spec=structure.path)
        case _:
            raise WrongItemKindError('a document or a skill entry')


def skill_fields_query(primitives: 'Primitives') -> SkillFields:
    """The independently parsed fields of a skill entry; empty for every other item."""
    if not isinstance(primitives.item_origin(), SkillEntryOrigin):
        return FrozenMapping({})
    return parse_skill_fields(primitives.frontmatter())


def schema_problems_query(primitives: 'Primitives') -> tuple[SchemaProblems, ...]:
    """What each applicable frontmatter schema rejects, with skill floor problems before corpus problems.

    Args:
        primitives: The model state of the document or skill.

    Returns:
        One entry per applicable schema, in order; none when no schema applies or frontmatter cannot be held to one.
    """
    origin = primitives.item_origin()
    governance = primitives.item_governance()
    schemas = governance.frontmatter_schemas() if governance is not None else ()
    if isinstance(origin, SkillEntryOrigin) and primitives.builtin_skills_schema():
        frontmatter = primitives.frontmatter()
        floor = locate_skill_schema_problems(frontmatter)
        governed = locate_schema_problems(frontmatter, schemas) if schemas else ()
        floor_missing = {
            (located.line, located.problem.field)
            for schema in floor
            for located in schema.problems
            if isinstance(located.problem, MissingFieldProblem)
        }
        return (
            *floor,
            *(
                SchemaProblems(
                    schema.source,
                    tuple(
                        located
                        for located in schema.problems
                        if not (
                            isinstance(located.problem, MissingFieldProblem)
                            and (located.line, located.problem.field) in floor_missing
                        )
                    ),
                )
                for schema in governed
            ),
        )
    if not schemas:
        return ()
    return locate_schema_problems(primitives.frontmatter(), schemas)
