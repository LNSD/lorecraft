"""Bundled schema inputs and their registration in a workspace's schema registry."""

from typing import Final

from lorecraft.core.mapping import FrozenMapping

from .agent_skills_frontmatter import SkillFrontmatter
from .types import BundledOrigin, SchemaInput, SchemaKind, SchemaReference

AGENT_SKILLS_SCHEMA_REFERENCE: Final[SchemaReference] = SchemaReference(
    SchemaKind.FRONTMATTER, 'builtin:agent-skills-frontmatter'
)
"""The stable schema subject for the bundled Agent Skills frontmatter floor."""

AGENT_SKILLS_SCHEMA_INPUT: Final[SchemaInput] = SchemaInput(
    AGENT_SKILLS_SCHEMA_REFERENCE,
    BundledOrigin('builtin:agent-skills-frontmatter'),
    FrozenMapping.from_plain(SkillFrontmatter.model_json_schema()),
)
"""The Agent Skills schema's JSON Schema representation, identity and bundled provenance."""


def register_builtin_schemas(schema_inputs: dict[SchemaReference, SchemaInput]) -> None:
    """Register the bundled schema inputs enabled for this workspace.

    Args:
        schema_inputs: The registry being assembled for the workspace model.
    """
    schema_inputs[AGENT_SKILLS_SCHEMA_REFERENCE] = AGENT_SKILLS_SCHEMA_INPUT
