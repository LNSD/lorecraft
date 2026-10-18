"""Derived frontmatter facts shared by the rules that inspect a document or skill entry."""

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import PathComponent
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.item import DocumentOrigin, ItemKind, SkillEntryOrigin, WrongItemKindError
from lorecraft.project.query.primitives import Primitives
from lorecraft.project.schemas import (
    DocumentFrontmatterOwner,
    FrontmatterOwner,
    SkillFields,
    SkillFrontmatterOwner,
    parse_skill_fields,
)


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
