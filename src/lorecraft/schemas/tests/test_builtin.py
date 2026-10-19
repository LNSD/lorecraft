"""Bundled schemas registered in a workspace model."""

import pytest

from lorecraft.schemas import (
    SchemaInput,
    SchemaReference,
)
from lorecraft.schemas.builtin import (
    AGENT_SKILLS_SCHEMA_INPUT,
    AGENT_SKILLS_SCHEMA_REFERENCE,
    register_builtin_schemas,
)


@pytest.mark.unit
class TestRegisterBuiltinSchemas:
    def test_register_adds_the_bundled_agent_skills_input(self) -> None:
        #: Given
        schema_inputs: dict[SchemaReference, SchemaInput] = {}

        #: When
        register_builtin_schemas(schema_inputs)

        #: Then
        assert schema_inputs == {AGENT_SKILLS_SCHEMA_REFERENCE: AGENT_SKILLS_SCHEMA_INPUT}, (
            'the bundled Agent Skills schema is registered with its stable identity and input'
        )
