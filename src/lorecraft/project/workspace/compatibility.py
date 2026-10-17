"""Analyze loaded namespace structures against ancestors as part of project-model derivation."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from lorecraft.core.mapping import Frozen
from lorecraft.project.aspect import AspectNamespace
from lorecraft.project.schemas import SectionEntry, StructureSpec
from lorecraft.project.schemas.structure import AnySections

from .model import Corpus


@dataclass(frozen=True, slots=True)
class StructureContradiction:
    """A contradiction between one namespace structure and one of its ancestors."""

    extension: StructureSpec
    base: StructureSpec
    detail: str


def compatibility_issues(corpus: Corpus) -> tuple[StructureContradiction, ...]:
    """Check loaded namespace structures against every loaded ancestor, including empty namespaces.

    The JSON Schema subset is literal `properties`, `required`, `additionalProperties: false`, `enum`, and
    `pattern`. Pattern satisfiability is tested only against finite enum values. Outline checks use named required
    sections and forbidden names; other JSON Schema and outline constructs are not analysed.
    """
    ancestors: list[tuple[AspectNamespace | None, StructureSpec]] = []
    if isinstance(corpus.corpus_spec.structure, StructureSpec):
        ancestors.append((None, corpus.corpus_spec.structure))
    issues: list[StructureContradiction] = []
    for namespace in corpus.namespace_specs:
        extension = namespace.structure
        if not isinstance(extension, StructureSpec):
            continue
        for namespace_name, base in ancestors:
            if namespace_name is not None and not namespace_name.is_prefix_of(namespace.name.namespace.value):
                continue
            issues.extend(_frontmatter_issues(base, extension))
            issues.extend(_outline_issues(base, extension))
        ancestors.append((namespace.name.namespace, extension))
    return tuple(issues)


def _frontmatter_issues(base: StructureSpec, extension: StructureSpec) -> list[StructureContradiction]:
    """Compare constraints on root properties that belong to the supported schema subset."""
    if base.frontmatter is None or extension.frontmatter is None:
        return []
    parent = base.frontmatter.schema
    child = extension.frontmatter.schema
    parent_properties = parent.get('properties', {})
    child_properties = child.get('properties', {})
    issues: list[StructureContradiction] = []
    if parent.get('additionalProperties') is False and isinstance(parent_properties, Mapping):
        required = child.get('required', ())
        for field in required if isinstance(required, tuple) else ():
            if field not in parent_properties:
                issues.append(
                    StructureContradiction(
                        extension, base, f'requires field {field!r}, which the base closed schema rejects'
                    )
                )
    if not isinstance(parent_properties, Mapping) or not isinstance(child_properties, Mapping):
        return issues
    for field, child_schema in child_properties.items():
        parent_schema = parent_properties.get(field)
        if not isinstance(parent_schema, Mapping) or not isinstance(child_schema, Mapping):
            continue
        parent_enum = parent_schema.get('enum')
        child_enum = child_schema.get('enum')
        if isinstance(child_enum, tuple):
            possible = [
                value
                for value in child_enum
                if (not isinstance(parent_enum, tuple) or value in parent_enum)
                and _pattern_accepts(parent_schema, value)
                and _pattern_accepts(child_schema, value)
            ]
            if not possible:
                issues.append(
                    StructureContradiction(extension, base, f'field {field!r} has no value allowed by its base')
                )
        elif isinstance(parent_enum, tuple) and isinstance(child_schema.get('pattern'), str):
            if not any(
                isinstance(value, str)
                and _pattern_accepts(child_schema, value)
                and _pattern_accepts(parent_schema, value)
                for value in parent_enum
            ):
                issues.append(
                    StructureContradiction(extension, base, f'field {field!r} pattern excludes every base enum value')
                )
    return issues


def _pattern_accepts(schema: Mapping[str, Frozen], value: object) -> bool:
    """Whether the supported pattern constraint accepts a finite enum value."""
    pattern = schema.get('pattern')
    return not isinstance(pattern, str) or not isinstance(value, str) or re.search(pattern, value) is not None


def _outline_issues(base: StructureSpec, extension: StructureSpec) -> list[StructureContradiction]:
    """Check required extension sections against base closure, forbiddance and named order."""
    required = [entry.name for entry in extension.outline if isinstance(entry, SectionEntry) and not entry.optional]
    forbidden = set(base.forbidden)
    results = [
        StructureContradiction(extension, base, f'requires section {section.value!r}, forbidden by its base')
        for section in required
        if section in forbidden
    ]
    if base.outline and not any(isinstance(entry, AnySections) for entry in base.outline):
        named = {entry.name for entry in base.outline if isinstance(entry, SectionEntry)}
        results.extend(
            StructureContradiction(
                extension, base, f'requires section {section.value!r}, absent from its closed base outline'
            )
            for section in required
            if section not in named and section not in forbidden
        )
    base_order = [entry.name for entry in base.outline if isinstance(entry, SectionEntry)]
    base_positions = {name: index for index, name in enumerate(base_order)}
    for index, before in enumerate(required):
        for after in required[index + 1 :]:
            if before in base_positions and after in base_positions and base_positions[before] > base_positions[after]:
                results.append(
                    StructureContradiction(
                        extension, base, f'requires {before.value!r} before {after.value!r}, opposite to its base'
                    )
                )
    return results
