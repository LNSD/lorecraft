"""Derived frontmatter facts shared by the rules that inspect a document or skill entry."""

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import PathComponent
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.item import DocumentOrigin, ItemKind, SkillEntryOrigin, WrongItemKindError
from lorecraft.project.query.primitives import Primitives
from lorecraft.project.schemas import (
    DocumentFrontmatterOwner,
    FrontmatterOwner,
    MissingFieldProblem,
    SchemaProblems,
    SkillFields,
    SkillFrontmatterOwner,
    locate_schema_problems,
    locate_skill_schema_problems,
    parse_skill_fields,
)
from lorecraft.project.syntax import Frontmatter


def frontmatter_owner(primitives: Primitives) -> FrontmatterOwner:
    """The document or skill entry whose frontmatter block the item opens.

    Args:
        primitives: The model state of the document or skill entry.

    Raises:
        WrongItemKindError: If the item is not a document whose corpus states a structure specification, or a
            skill entry.
    """
    descriptor = primitives.item_descriptor()
    assert descriptor is not None, 'a query over the owner runs over decoded text'
    match descriptor.origin:
        case SkillEntryOrigin():
            return SkillFrontmatterOwner(
                directory_name=PathComponent.parse(descriptor.origin.expected_name),
                link_target=descriptor.origin.link_target,
            )
        case DocumentOrigin():
            specs = primitives.structure_specs()
            if not specs:
                raise WrongItemKindError(descriptor.ref, 'a document whose corpus states a structure specification')
            return DocumentFrontmatterOwner(
                filename=AspectFilename.parse(descriptor.origin.expected_name), spec=specs[0].path
            )
        case _:
            raise WrongItemKindError(descriptor.ref, 'a document or a skill entry')


def skill_fields(primitives: Primitives) -> SkillFields:
    """The parsed fields of a skill entry's frontmatter, or empty for any other item.

    Args:
        primitives: The model state of the item.
    """
    descriptor = primitives.item_descriptor()
    if descriptor is None or descriptor.kind is not ItemKind.SKILL_ENTRY:
        return FrozenMapping({})
    return parse_skill_fields(primitives.frontmatter())


def schema_problems(primitives: Primitives) -> tuple[SchemaProblems, ...]:
    """What each schema governing the item rejects in its frontmatter, preserving schema order.

    Args:
        primitives: The model state of the document or skill entry.
    """
    descriptor = primitives.item_descriptor()
    if descriptor is None:
        return ()
    schemas = primitives.frontmatter_schemas()
    skills = descriptor.kind is ItemKind.SKILL_ENTRY
    builtin = skills and primitives.builtin_skills_schema()
    if not schemas and not builtin:
        return ()
    frontmatter = primitives.frontmatter()
    if not isinstance(frontmatter, Frontmatter):
        return ()

    # The fixed Agent Skills floor comes first; configured skill schemas can only add constraints.
    floor = locate_skill_schema_problems(frontmatter) if builtin else ()
    governed = locate_schema_problems(frontmatter, schemas) if schemas else ()
    if not floor:
        return governed
    floor_missing = {
        (located.line, located.problem.field)
        for problem_set in floor
        for located in problem_set.problems
        if isinstance(located.problem, MissingFieldProblem)
    }
    governed = tuple(
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
    )
    return (*floor, *governed)
