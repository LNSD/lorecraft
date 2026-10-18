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
