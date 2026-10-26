"""Project queries over frontmatter ownership and parsed skill fields."""

from collections.abc import Callable
from dataclasses import replace
from typing import cast

import pytest

from lib.primitives import StructurePrimitives
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import PathComponent
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.item import DocumentOrigin, ItemDescriptor, SkillEntrypointOrigin, WrongItemTypeError
from lorecraft.project.query.primitives import QueryTargetRef
from lorecraft.project.schemas.frontmatter_owner import SkillFrontmatterOwner
from lorecraft.project.schemas.frontmatter_queries import (
    UnhandledFrontmatterSchemaInputError,
    frontmatter_schema_problems,
    parsed_skill_fields,
)
from lorecraft.project.schemas.skill_fields import SkillField, SkillName
from lorecraft.project.syntax import parse_frontmatter
from lorecraft.schemas import BuiltinOrigin, SchemaInput, SchemaKind, SchemaRef
from lorecraft.schemas.types import SchemaOrigin

from ..frontmatter_queries import owner_of_frontmatter

# SAFETY: the schema query test deliberately supplies an origin outside the closed runtime variants.
_UNHANDLED_SCHEMA_ORIGIN = cast(SchemaOrigin, object())


@pytest.mark.unit
class TestOwnerOfFrontmatter:
    def test_owner_of_frontmatter_with_a_document_without_corpus_structure_raises_wrong_item_type_error(self) -> None:
        #: Given
        expected_error = WrongItemTypeError
        primitives = StructurePrimitives(
            (),
            origin_value=DocumentOrigin(),
            name=AspectFilename.parse('guide'),
            corpus=CorpusName.parse('guide'),
        )

        #: When
        with pytest.raises(expected_error) as exc_info:
            owner_of_frontmatter(primitives)

        #: Then
        assert exc_info.type is expected_error, 'a document without a structure spec raises the exact typed error'

    def test_owner_of_frontmatter_with_a_skill_entrypoint_origin_returns_the_skill_owner(self) -> None:
        #: Given
        primitives = StructurePrimitives(
            (),
            origin_value=SkillEntrypointOrigin(link_target=None),
            name=AspectFilename.parse('review'),
        )

        #: When
        owner = owner_of_frontmatter(primitives)

        #: Then
        assert owner == SkillFrontmatterOwner(PathComponent.parse('review'), None), (
            'the builtin frontmatter floor identifies the skill owner'
        )


@pytest.mark.unit
class TestParsedSkillFields:
    def test_parsed_skill_fields_with_the_builtin_floor_reads_the_name(self) -> None:
        #: Given
        primitives = StructurePrimitives(
            (),
            origin_value=SkillEntrypointOrigin(link_target=None),
            name=AspectFilename.parse('review'),
            frontmatter_node=parse_frontmatter('---\nname: review\n---\n'),
        )

        #: When
        fields = parsed_skill_fields(primitives)

        #: Then
        assert fields == FrozenMapping({SkillField.NAME: SkillName.parse('review')}), (
            'skill fields are read when the descriptor includes the builtin floor schema'
        )


@pytest.mark.unit
class TestFrontmatterSchemaProblems:
    @pytest.mark.parametrize(
        ('kind', 'identity', 'builtin_origin'),
        [
            (SchemaKind.STRUCTURE, 'unsupported', True),
            (SchemaKind.FRONTMATTER, 'builtin:other', True),
            (SchemaKind.FRONTMATTER, 'repository-missing-origin', False),
        ],
        ids=('unhandled-kind', 'unhandled-builtin', 'unhandled-origin'),
    )
    def test_frontmatter_schema_problems_with_an_unhandled_input_raises_at_the_registry_boundary(
        self, kind: SchemaKind, identity: str, builtin_origin: bool
    ) -> None:
        #: Given
        reference = SchemaRef(kind, identity)
        origin = BuiltinOrigin(identity) if builtin_origin else _UNHANDLED_SCHEMA_ORIGIN
        schema = SchemaInput(reference, origin, FrozenMapping({}))

        class UnhandledSchemaPrimitives:
            def schema_input(self) -> SchemaInput:
                return schema

        class WrongInputPrimitives(StructurePrimitives):
            def descriptor(self) -> ItemDescriptor:
                return replace(super().descriptor(), frontmatter_schema_refs=(reference,))

            def query_at[T](self, ref: QueryTargetRef, query: Callable[..., T]) -> T:
                if ref == reference:
                    return query(UnhandledSchemaPrimitives())
                return super().query_at(ref, query)

        primitives = WrongInputPrimitives(
            (),
            origin_value=SkillEntrypointOrigin(link_target=None),
            frontmatter_node=parse_frontmatter('---\nname: value\n---\n'),
        )

        #: When
        with pytest.raises(UnhandledFrontmatterSchemaInputError) as exc_info:
            frontmatter_schema_problems(primitives)

        #: Then
        assert exc_info.value.schema == schema, 'the error identifies the unsupported registered schema input'
