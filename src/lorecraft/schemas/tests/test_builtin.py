"""Builtin schemas registered in a workspace model."""

import pytest

from lorecraft.schemas import BundledOrigin
from lorecraft.schemas.builtin import (
    AGENT_SKILLS_SCHEMA_INPUT,
    AGENT_SKILLS_SCHEMA_REFERENCE,
)


@pytest.mark.unit
class TestBuiltinSchemaInput:
    def test_agent_skills_input_has_its_stable_reference_and_builtin_origin(self) -> None:
        #: Given
        schema_input = AGENT_SKILLS_SCHEMA_INPUT

        #: When
        #: Then
        assert schema_input.reference == AGENT_SKILLS_SCHEMA_REFERENCE, 'the input uses its declared reference'
        assert isinstance(schema_input.origin, BundledOrigin), 'the input declares builtin provenance'
        assert schema_input.origin.identity == AGENT_SKILLS_SCHEMA_REFERENCE.identity, (
            'the input provenance matches its stable identity'
        )
