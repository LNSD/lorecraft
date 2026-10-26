"""Builtin schemas registered in a workspace model."""

import pytest

from lorecraft.core.mapping import FrozenMapping
from lorecraft.schemas import BuiltinOrigin, FrontmatterSchemaInput, SchemaKind, SchemaRef
from lorecraft.schemas.builtin import (
    AGENT_SKILLS_SCHEMA_INPUT,
    AGENT_SKILLS_SCHEMA_REFERENCE,
)


@pytest.mark.unit
class TestBuiltinSchemaInput:
    def test_frontmatter_schema_input_has_a_fixed_frontmatter_kind(self) -> None:
        #: Given
        schema_input = FrontmatterSchemaInput(BuiltinOrigin('builtin:test'), FrozenMapping({}))

        #: When
        reference = schema_input.reference

        #: Then
        assert schema_input.kind is SchemaKind.FRONTMATTER, 'the input cannot declare another schema kind'
        assert reference == SchemaRef(SchemaKind.FRONTMATTER, 'builtin:test'), (
            'the reference uses the fixed kind and supplied builtin identity'
        )

    def test_agent_skills_input_has_its_stable_reference_and_builtin_origin(self) -> None:
        #: Given
        schema_input = AGENT_SKILLS_SCHEMA_INPUT

        #: When
        #: Then
        assert schema_input.reference == AGENT_SKILLS_SCHEMA_REFERENCE, 'the input derives its reference from origin'
        assert isinstance(schema_input.origin, BuiltinOrigin), 'the input declares builtin provenance'
        assert schema_input.origin.identity == AGENT_SKILLS_SCHEMA_REFERENCE.identity, (
            'the input provenance matches its stable identity'
        )
