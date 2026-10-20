"""The schema inputs Lorecraft ships as builtin definitions."""

from typing import Final

from lorecraft.core.mapping import FrozenMapping

from .agent_skills_frontmatter import SkillFrontmatter
from .types import BundledOrigin, SchemaInput, SchemaKind, SchemaRef

AGENT_SKILLS_SCHEMA_REFERENCE: Final[SchemaRef] = SchemaRef(SchemaKind.FRONTMATTER, 'builtin:agent-skills-frontmatter')
"""The stable schema subject for the builtin Agent Skills frontmatter floor."""

AGENT_SKILLS_SCHEMA_INPUT: Final[SchemaInput] = SchemaInput(
    AGENT_SKILLS_SCHEMA_REFERENCE,
    BundledOrigin('builtin:agent-skills-frontmatter'),
    FrozenMapping.from_plain(SkillFrontmatter.model_json_schema()),
)
"""The Agent Skills schema's JSON Schema representation, identity and builtin provenance."""
