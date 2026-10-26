"""Builtin specification layers enabled by default."""

from typing import Final

from lorecraft.project.item import ItemType
from lorecraft.schemas.builtin import AGENT_SKILLS_SCHEMA_INPUT, AGENT_SKILLS_SCHEMA_ORIGIN

from .model import BuiltinSpecLayer

AGENT_SKILLS_SPEC_LAYER: Final[BuiltinSpecLayer] = BuiltinSpecLayer(
    AGENT_SKILLS_SCHEMA_ORIGIN,
    frozenset({ItemType.SKILL_ENTRYPOINT}),
    frontmatter_schema=AGENT_SKILLS_SCHEMA_INPUT,
)
"""The builtin Agent Skills frontmatter floor, applied before repository layers."""
