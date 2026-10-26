"""The schema inputs Lorecraft ships as builtin definitions."""

from typing import Final

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.text import NonEmptyStr

from .agent_skills_frontmatter import SkillFrontmatter
from .types import BuiltinOrigin, FrontmatterSchemaInput, SchemaRef

AGENT_SKILLS_LAYER_ORIGIN: Final[BuiltinOrigin] = BuiltinOrigin(NonEmptyStr.parse('builtin:agent-skills'))
"""The stable identity of the Agent Skills specification layer."""

AGENT_SKILLS_SCHEMA_INPUT: Final[FrontmatterSchemaInput] = FrontmatterSchemaInput(
    BuiltinOrigin(NonEmptyStr.parse('builtin:agent-skills-frontmatter')),
    FrozenMapping.from_plain(SkillFrontmatter.model_json_schema()),
)
"""The Agent Skills schema's JSON Schema representation, identity and builtin provenance."""

AGENT_SKILLS_SCHEMA_REFERENCE: Final[SchemaRef] = AGENT_SKILLS_SCHEMA_INPUT.reference
"""The stable schema subject for the builtin Agent Skills frontmatter floor."""
