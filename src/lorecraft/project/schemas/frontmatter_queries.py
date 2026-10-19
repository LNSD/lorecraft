"""Facts of a frontmatter block, derived from raw syntax and governance primitives."""

from typing import TYPE_CHECKING

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import PathComponent
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.item import DocumentOrigin, SkillEntrypointOrigin, WrongItemKindError
from lorecraft.project.query import item_frontmatter
from lorecraft.project.schemas.agent_skills_schema import agent_skills_frontmatter_schema
from lorecraft.project.schemas.frontmatter_owner import (
    DocumentFrontmatterOwner,
    FrontmatterOwner,
    SkillFrontmatterOwner,
)
from lorecraft.project.schemas.schema_problems import (
    MissingFieldProblem,
    SchemaProblems,
    locate_agent_skills_schema_problems,
    locate_schema_problems,
)
from lorecraft.project.schemas.skill_fields import SkillFields, parse_skill_fields
from lorecraft.schemas import SchemaRefError
from lorecraft.schemas.builtin import AGENT_SKILLS_SCHEMA_REFERENCE

if TYPE_CHECKING:
    from lorecraft.project.query import GovernancePrimitives, ItemPrimitives


def owner_of_frontmatter(primitives: GovernancePrimitives) -> FrontmatterOwner:
    """The document or skill whose frontmatter the item opens, from origin metadata and governance.

    Raises:
        WrongItemKindError: If the item is not a skill or a document whose corpus states a structure spec.
    """
    origin = primitives.origin()
    match origin:
        case SkillEntrypointOrigin():
            return SkillFrontmatterOwner(
                directory_name=PathComponent.parse(origin.expected_name), link_target=origin.link_target
            )
        case DocumentOrigin():
            governance = primitives.governance()
            structure = governance.corpus_structure() if governance is not None else None
            if structure is None:
                raise WrongItemKindError('a document whose corpus states a structure specification')
            return DocumentFrontmatterOwner(filename=AspectFilename.parse(origin.expected_name), spec=structure.path)
        case _:
            raise WrongItemKindError('a document or a skill entrypoint')


def parsed_skill_fields(primitives: ItemPrimitives) -> SkillFields:
    """The independently parsed fields of a skill; empty for every other item."""
    if not isinstance(primitives.origin(), SkillEntrypointOrigin):
        return FrozenMapping({})
    return parse_skill_fields(primitives.query(item_frontmatter))


def frontmatter_schema_problems(primitives: ItemPrimitives) -> tuple[SchemaProblems, ...]:
    """What each applicable frontmatter schema rejects, with skill floor problems before corpus problems.

    Args:
        primitives: The model state of the document or skill.

    Returns:
        One entry per applicable schema, in order; none when no schema applies or frontmatter cannot be held to one.
    """
    origin = primitives.origin()
    governance = primitives.governance()
    schemas = governance.frontmatter_schemas() if governance is not None else ()
    if isinstance(origin, SkillEntrypointOrigin):
        frontmatter = primitives.query(item_frontmatter)
        floor_present = False
        try:
            floor_schema = primitives.query_schema(AGENT_SKILLS_SCHEMA_REFERENCE, agent_skills_frontmatter_schema)
        except SchemaRefError:
            floor = ()
        else:
            floor_present = True
            floor = locate_agent_skills_schema_problems(frontmatter, floor_schema)
        governed = locate_schema_problems(frontmatter, schemas) if schemas else ()
        floor_missing = {
            (located.line, located.problem.field)
            for schema in floor
            for located in schema.problems
            if isinstance(located.problem, MissingFieldProblem)
        }
        if not floor_present:
            return governed
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
    return locate_schema_problems(primitives.query(item_frontmatter), schemas)
