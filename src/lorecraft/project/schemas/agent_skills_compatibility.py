"""Bounded compatibility checks between repository schemas and required Agent Skills fields."""

from collections.abc import Mapping
from dataclasses import dataclass

from lorecraft.core.mapping import Plain
from lorecraft.schemas.agent_skills_frontmatter import (
    EmptySkillDescriptionError,
    EmptySkillNameError,
    InvalidSkillNameFormatError,
    OverlongSkillDescriptionError,
    OverlongSkillNameError,
    SkillDescription,
    SkillName,
)


@dataclass(frozen=True, slots=True)
class AgentSkillsSchemaContradiction:
    """One direct property constraint that excludes a required Agent Skills field rule."""

    field: str
    rule: str


_FIELD_RULES = {
    'name': ('skill name must be lowercase letters, digits and single hyphens', 1, 64),
    'description': ('skill description must contain non-whitespace text and be at most 1024 characters', 1, 1024),
}


def agent_skills_schema_contradictions(schema: Mapping[str, Plain]) -> tuple[AgentSkillsSchemaContradiction, ...]:
    """Find directly stated required-field contradictions within the agreed bounded analysis.

    Args:
        schema: The plain frontmatter schema from a skills corpus layer.
    """
    properties = schema.get('properties')
    if not isinstance(properties, dict):
        return ()
    found: list[AgentSkillsSchemaContradiction] = []
    for field, (rule, floor_min, floor_max) in _FIELD_RULES.items():
        constraint = properties.get(field)
        if constraint is None:
            continue
        if constraint is False:
            found.append(AgentSkillsSchemaContradiction(field, rule))
            continue
        if not isinstance(constraint, dict):
            continue
        types = constraint.get('type')
        if types is not None:
            allowed_types = types if isinstance(types, list) else [types]
            if 'string' not in allowed_types:
                found.append(AgentSkillsSchemaContradiction(field, rule))
                continue
        minimum = _bound(constraint.get('minLength'), floor_min)
        maximum = _bound(constraint.get('maxLength'), floor_max)
        if max(floor_min, minimum) > min(floor_max, maximum):
            found.append(AgentSkillsSchemaContradiction(field, rule))
            continue
        candidates = constraint.get('enum')
        if candidates is not None and not isinstance(candidates, list):
            continue
        if 'const' in constraint:
            if candidates is None:
                candidates = [constraint['const']]
            else:
                candidates = [item for item in candidates if item == constraint['const']]
        if isinstance(candidates, list):
            if not any(_satisfies(field, candidate, constraint, floor_min, floor_max) for candidate in candidates):
                found.append(AgentSkillsSchemaContradiction(field, rule))
    return tuple(found)


def _satisfies(field: str, candidate: Plain, schema: Mapping[str, Plain], floor_min: int, floor_max: int) -> bool:
    if not isinstance(candidate, str):
        return False
    minimum = _bound(schema.get('minLength'), floor_min)
    maximum = _bound(schema.get('maxLength'), floor_max)
    if len(candidate) < minimum or len(candidate) > maximum:
        return False
    try:
        if field == 'name':
            SkillName.parse(candidate)
        else:
            SkillDescription.parse(candidate)
    except (
        EmptySkillDescriptionError,
        EmptySkillNameError,
        InvalidSkillNameFormatError,
        OverlongSkillDescriptionError,
        OverlongSkillNameError,
    ):
        return False
    return True


def _bound(value: Plain | None, floor: int) -> int:
    """Use a direct integer length constraint, or the built-in bound when it is not an integer."""
    return value if isinstance(value, int) and not isinstance(value, bool) else floor
