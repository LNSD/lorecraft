"""Builtin specification layers shipped with Lorecraft."""

from typing import Final

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.project.item import ItemType
from lorecraft.schemas.builtin import AGENT_SKILLS_LAYER_ORIGIN, AGENT_SKILLS_SCHEMA_INPUT

from .model import BuiltinSpecLayer

AGENT_SKILLS_LINE_BUDGET: Final[NonZeroUnsignedInt] = NonZeroUnsignedInt(500)
"""The default line budget for an Agent Skills entrypoint."""

AGENT_SKILLS_SPEC_LAYER: Final[BuiltinSpecLayer] = BuiltinSpecLayer(
    AGENT_SKILLS_LAYER_ORIGIN,
    frozenset({ItemType.SKILL_ENTRYPOINT}),
    frontmatter_schema=AGENT_SKILLS_SCHEMA_INPUT,
    lines=AGENT_SKILLS_LINE_BUDGET,
)
"""The builtin Agent Skills floor, with frontmatter schema and line budget, applied before repository layers."""
