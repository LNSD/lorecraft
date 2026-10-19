"""Tests for schema identity and pure registry resolution."""

import pytest

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import RootRelativePath
from lorecraft.schemas import (
    BundledOrigin,
    DuplicateSchemaRefError,
    EmptyBundledOriginIdentityError,
    EmptyRepositoryLayerError,
    EmptySchemaRefIdentityError,
    RepositoryOrigin,
    SchemaInput,
    SchemaKind,
    SchemaOriginMismatchError,
    SchemaRef,
    SchemaRefError,
    SchemaRegistry,
)


def _repository_schema(identity: str, kind: SchemaKind = SchemaKind.STRUCTURE) -> SchemaInput:
    return SchemaInput(
        reference=SchemaRef(kind, identity),
        origin=RepositoryOrigin(RootRelativePath.parse(f'docs/{identity}.yaml'), 'global'),
        document=FrozenMapping.from_plain({'type': 'object'}),
    )


@pytest.mark.unit
class TestSchemaRegistry:
    def test_resolve_with_registered_reference_returns_input(self) -> None:
        #: Given
        schema_input = _repository_schema('base')
        registry = SchemaRegistry.from_inputs((schema_input,))

        #: When
        resolved = registry.resolve(schema_input.reference)

        #: Then
        assert resolved is schema_input, 'resolution returns the loaded immutable input'

    def test_resolve_with_unknown_reference_raises(self) -> None:
        #: Given
        registry = SchemaRegistry.from_inputs(())
        reference = SchemaRef(SchemaKind.FRONTMATTER, 'guide')

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
    def test_bundled_origin_can_back_any_schema_kind(self, kind: SchemaKind) -> None:
        #: Given
        reference = SchemaRef(kind, 'agent-skills')
        origin = BundledOrigin('agent-skills')
        document = FrozenMapping.from_plain({'type': 'object'})

        #: When
        schema_input = SchemaInput(
            reference=reference,
            origin=origin,
            document=document,
        )

        #: Then
        assert schema_input.origin is origin, 'bundled provenance needs no repository path'

    def test_bundled_input_with_different_origin_identity_raises(self) -> None:
        #: Given
        reference = SchemaRef(SchemaKind.STRUCTURE, 'agent-skills')
        origin = BundledOrigin('other-builtin')
        document = FrozenMapping.from_plain({'type': 'object'})

        #: When
        with pytest.raises(SchemaOriginMismatchError) as exc_info:
            SchemaInput(reference=reference, origin=origin, document=document)

        #: Then
        assert exc_info.value.reference == reference, 'the refusal identifies the mismatched reference'
        assert exc_info.value.origin == origin, 'the refusal preserves the mismatched origin'

    def test_schema_kinds_remain_distinct_for_the_same_identity(self) -> None:
        #: Given
        structure = _repository_schema('same', SchemaKind.STRUCTURE)
        frontmatter = _repository_schema('same', SchemaKind.FRONTMATTER)

        #: When
        references_differ = structure.reference != frontmatter.reference

        #: Then
        assert references_differ, 'kind is part of schema identity'


@pytest.mark.unit
class TestSchemaRef:
    def test_reference_with_empty_identity_raises_typed_error(self) -> None:
        #: Given
        kind = SchemaKind.STRUCTURE
        identity = ''

        #: When
        with pytest.raises(EmptySchemaRefIdentityError) as exc_info:
            SchemaRef(kind, identity)

        #: Then
        assert exc_info.value.kind is kind, 'the refusal identifies the schema kind'
        assert exc_info.value.identity == identity, 'the refusal preserves the empty identity'


@pytest.mark.unit
class TestRepositoryOrigin:
    def test_origin_with_empty_layer_raises_typed_error(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/structure.yaml')
        layer = ''

        #: When
        with pytest.raises(EmptyRepositoryLayerError) as exc_info:
            RepositoryOrigin(path, layer)

        #: Then
        assert exc_info.value.path == path, 'the refusal identifies the repository input'
        assert exc_info.value.layer == layer, 'the refusal preserves the empty layer'


@pytest.mark.unit
class TestBundledOrigin:
    def test_origin_with_empty_identity_raises_typed_error(self) -> None:
        #: Given
        identity = ''

        #: When
        with pytest.raises(EmptyBundledOriginIdentityError) as exc_info:
            BundledOrigin(identity)

        #: Then
        assert exc_info.value.identity == identity, 'the refusal preserves the empty bundled identity'
