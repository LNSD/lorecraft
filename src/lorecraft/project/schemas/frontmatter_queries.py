"""Facts of a frontmatter block, derived from raw syntax and governance primitives."""

from dataclasses import replace
from typing import TYPE_CHECKING

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import PathComponent
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.item import SkillEntrypointOrigin, WrongItemTypeError
from lorecraft.project.query import item_frontmatter, item_name
from lorecraft.project.schemas.agent_skills_schema import (
    agent_skills_frontmatter_schema,
)
from lorecraft.project.schemas.frontmatter_owner import (
    DocumentFrontmatterOwner,
    FrontmatterOwner,
    SkillFrontmatterOwner,
)
from lorecraft.project.schemas.frontmatter_problem import MissingFieldProblem
from lorecraft.project.schemas.frontmatter_schema import FrontmatterSchema
from lorecraft.project.schemas.schema_problems import (
    SchemaProblems,
    locate_agent_skills_schema_problems,
    locate_repository_schema_problems,
)
from lorecraft.project.schemas.skill_fields import SkillFields, parse_skill_fields
from lorecraft.schemas import BundledOrigin, RepositoryOrigin, SchemaInput

if TYPE_CHECKING:
    from lorecraft.project.query import GovernancePrimitives, ItemPrimitives, SchemaPrimitives


def read_schema_input(primitives: SchemaPrimitives) -> SchemaInput:
    """The input registered for one frontmatter schema subject."""
    return primitives.schema_input()


def repository_frontmatter_schema(primitives: SchemaPrimitives) -> FrontmatterSchema:
    """The checked repository frontmatter schema from its registry input."""
    schema_input = primitives.schema_input()
    assert isinstance(schema_input.document, FrozenMapping)
    return FrontmatterSchema(schema_input.document)


def owner_of_frontmatter(primitives: GovernancePrimitives) -> FrontmatterOwner:
    """The document or skill whose frontmatter the item opens, from its descriptor and governance.

    Raises:
        WrongItemTypeError: If the item is not a skill or a document whose corpus states a structure spec.
    """
    origin = primitives.origin()
    if isinstance(origin, SkillEntrypointOrigin):
        return SkillFrontmatterOwner(
            directory_name=PathComponent.parse(primitives.item_listed_name()), link_target=origin.link_target
        )
    name = primitives.query(item_name)
    governance = primitives.governance()
    if isinstance(name, AspectFilename) and governance is not None:
        structure = governance.corpus_structure()
        if structure is not None:
            return DocumentFrontmatterOwner(filename=name, spec=structure.path)
    raise WrongItemTypeError('a document whose corpus states a structure specification')


def parsed_skill_fields(primitives: ItemPrimitives) -> SkillFields:
    """The independently parsed fields of a skill; empty for every other item."""
    if not isinstance(primitives.origin(), SkillEntrypointOrigin):
        return FrozenMapping({})
    return parse_skill_fields(primitives.query(item_frontmatter))


def frontmatter_schema_problems(primitives: ItemPrimitives) -> tuple[SchemaProblems, ...]:
    """What every applicable frontmatter schema rejects, one result per schema, with progressive deduplication.

    Args:
        primitives: The model state of the document or skill.

    Returns:
        One entry per applicable schema, in order; none when no schema applies or frontmatter cannot be held to one.
    """
    refs = primitives.item_descriptor().frontmatter_schema_refs
    if not refs:
        return ()
    frontmatter = primitives.query(item_frontmatter)
    found: list[SchemaProblems] = []
    earlier_missing: set[tuple[int, str]] = set()
    for reference in refs:
        schema = primitives.query_at(reference, read_schema_input)
        if isinstance(schema.origin, BundledOrigin):
            schema = primitives.query_at(reference, agent_skills_frontmatter_schema)
            located = locate_agent_skills_schema_problems(frontmatter, schema)
        else:
            if not isinstance(schema.origin, RepositoryOrigin):
                continue
            repository_schema = primitives.query_at(reference, repository_frontmatter_schema)
            located = locate_repository_schema_problems(frontmatter, repository_schema, schema.origin.path)
        problems = tuple(
            problem
            for result in located
            for problem in result.problems
            if not isinstance(problem.problem, MissingFieldProblem)
            or (problem.line.value, problem.problem.field) not in earlier_missing
        )
        found.extend(replace(result, problems=problems) for result in located)
        earlier_missing.update(
            (problem.line.value, problem.problem.field)
            for result in located
            for problem in result.problems
            if isinstance(problem.problem, MissingFieldProblem)
        )
    return tuple(found)
