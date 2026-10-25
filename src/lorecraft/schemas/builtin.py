"""The schema inputs Lorecraft ships as builtin definitions."""

from typing import Final

from lorecraft.core.mapping import FrozenMapping

from .agent_skills_frontmatter import SkillFrontmatter
from .types import BuiltinOrigin, SchemaInput, SchemaKind, SchemaRef

AGENT_SKILLS_SCHEMA_REFERENCE: Final[SchemaRef] = SchemaRef(SchemaKind.FRONTMATTER, 'builtin:agent-skills-frontmatter')
"""The stable schema subject for the builtin Agent Skills frontmatter floor."""

AGENT_SKILLS_SCHEMA_ORIGIN: Final[BuiltinOrigin] = BuiltinOrigin('builtin:agent-skills-frontmatter')
"""The stable builtin identity of the Agent Skills frontmatter schema."""

AGENT_SKILLS_LAYER_ORIGIN: Final[BuiltinOrigin] = BuiltinOrigin('builtin:agent-skills')
"""The stable identity of the Agent Skills specification layer."""

AGENT_SKILLS_SCHEMA_INPUT: Final[SchemaInput] = SchemaInput(
    AGENT_SKILLS_SCHEMA_REFERENCE,
    AGENT_SKILLS_SCHEMA_ORIGIN,
    FrozenMapping.from_plain(SkillFrontmatter.model_json_schema()),
)
"""The Agent Skills schema's JSON Schema representation, identity and builtin provenance."""
