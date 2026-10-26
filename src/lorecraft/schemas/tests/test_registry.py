"""Tests for schema identity and pure registry resolution."""

import pytest

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import RootRelativePath
from lorecraft.core.text import NonEmptyStr
from lorecraft.schemas import (
    BuiltinOrigin,
    BuiltinSchemaInput,
    DuplicateSchemaRefError,
    RepositoryOrigin,
    RepositorySchemaInput,
    SchemaInput,
    SchemaKind,
    SchemaRef,
    SchemaRefError,
    SchemaRegistry,
)


def _repository_schema(identity: str, kind: SchemaKind = SchemaKind.STRUCTURE) -> SchemaInput:
    return RepositorySchemaInput(
        reference=SchemaRef(kind, NonEmptyStr.parse(identity)),
        origin=RepositoryOrigin(RootRelativePath.parse(f'docs/{identity}.yaml'), NonEmptyStr.parse('global')),
        document=FrozenMapping.from_plain({'type': 'object'}),
    )


class TestSchemaRegistry:
    def test_resolve_with_registered_reference_returns_input(self) -> None:
        #: Given
        schema_input = _repository_schema('base')
        registry = SchemaRegistry.from_inputs((schema_input,))

        #: When
        resolved = registry.resolve(schema_input.reference)

        #: Then
        assert resolved is schema_input, 'resolution returns the loaded immutable input'
        assert registry.inputs == FrozenMapping({schema_input.reference: schema_input}), (
            'registry inputs are keyed by their typed references'
        )

    def test_resolve_with_unknown_reference_raises(self) -> None:
        #: Given
        registry = SchemaRegistry.from_inputs(())
        reference = SchemaRef(SchemaKind.FRONTMATTER, NonEmptyStr.parse('guide'))

        #: When
        with pytest.raises(SchemaRefError) as exc_info:
            registry.resolve(reference)

        #: Then
        assert exc_info.value.reference == reference, 'the refusal identifies the missing schema'

    def test_registry_with_duplicate_reference_raises(self) -> None:
        #: Given
        schema_input = _repository_schema('base')

        #: When
        with pytest.raises(DuplicateSchemaRefError) as exc_info:
            SchemaRegistry.from_inputs((schema_input, schema_input))

        #: Then
        assert exc_info.value.reference == schema_input.reference, 'the refusal identifies the collision'

    @pytest.mark.parametrize('kind', [SchemaKind.STRUCTURE, SchemaKind.FRONTMATTER])
    def test_builtin_origin_can_back_any_schema_kind(self, kind: SchemaKind) -> None:
        #: Given
        identity = 'agent-skills'
        origin = BuiltinOrigin(NonEmptyStr.parse(identity))
        document = FrozenMapping.from_plain({'type': 'object'})

        #: When
        schema_input = BuiltinSchemaInput(
            kind=kind,
            origin=origin,
            document=document,
        )

        #: Then
        assert schema_input.origin is origin, 'builtin provenance needs no repository path'

    def test_builtin_input_derives_its_reference_from_its_origin(self) -> None:
        #: Given
        kind = SchemaKind.STRUCTURE
        origin = BuiltinOrigin(NonEmptyStr.parse('agent-skills'))
        document = FrozenMapping.from_plain({'type': 'object'})

        #: When
        schema_input = BuiltinSchemaInput(kind=kind, origin=origin, document=document)

        #: Then
        assert schema_input.reference == SchemaRef(kind, origin.identity), 'the reference uses the origin identity once'

    def test_schema_kinds_remain_distinct_for_the_same_identity(self) -> None:
        #: Given
        structure = _repository_schema('same', SchemaKind.STRUCTURE)
        frontmatter = _repository_schema('same', SchemaKind.FRONTMATTER)

        #: When
        references_differ = structure.reference != frontmatter.reference

        #: Then
        assert references_differ, 'kind is part of schema identity'

    def test_schema_references_sort_by_identity(self) -> None:
        #: Given
        later = SchemaRef(SchemaKind.FRONTMATTER, NonEmptyStr.parse('b'))
        earlier = SchemaRef(SchemaKind.FRONTMATTER, NonEmptyStr.parse('a'))

        #: When
        references = sorted((later, earlier))

        #: Then
        assert references == [earlier, later], 'references with the same kind sort by their identity'
