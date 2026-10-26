"""Builtin schema inputs and their registration in a workspace's schema registry."""

from typing import Final

from lorecraft.core.mapping import FrozenMapping

from .agent_skills_frontmatter import SkillFrontmatter
from .types import BuiltinOrigin, SchemaInput, SchemaKind, SchemaRef

AGENT_SKILLS_SCHEMA_REFERENCE: Final[SchemaRef] = SchemaRef(SchemaKind.FRONTMATTER, 'builtin:agent-skills-frontmatter')
"""The stable schema subject for the builtin Agent Skills frontmatter floor."""

AGENT_SKILLS_SCHEMA_INPUT: Final[SchemaInput] = SchemaInput(
    AGENT_SKILLS_SCHEMA_REFERENCE,
    BuiltinOrigin('builtin:agent-skills-frontmatter'),
    FrozenMapping.from_plain(SkillFrontmatter.model_json_schema()),
)
"""The Agent Skills schema's JSON Schema representation, identity and builtin provenance."""


def register_builtin_schemas(schema_inputs: dict[SchemaRef, SchemaInput]) -> None:
    """Register the builtin schema inputs enabled for this workspace.

    Args:
        schema_inputs: The registry being assembled for the workspace model.
    """
    schema_inputs[AGENT_SKILLS_SCHEMA_REFERENCE] = AGENT_SKILLS_SCHEMA_INPUT
