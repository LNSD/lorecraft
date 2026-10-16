"""Inspect schema validity and the references the accepted dialect applies to one instance."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Final

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

from lorecraft.core.error import Unreachable
from lorecraft.core.mapping import Plain

from .dialect import DIALECT


@dataclass(frozen=True, slots=True)
class SchemaMetaError:
    """The schema does not satisfy the accepted dialect's meta-schema.

    Attributes:
        message: The validator's meta-schema refusal text, retained verbatim for the project diagnostic.
    """

    message: str


@dataclass(frozen=True, slots=True)
class SchemaHasIdentifier:
    """A schema sets `$id`, making a resource with a new reference base."""


@dataclass(frozen=True, slots=True)
class SchemaUsesForeignDialect:
    """A schema names a dialect other than the one the package accepts.

    Attributes:
        dialect: The unsupported dialect URI as written in the schema.
    """

    dialect: str


@dataclass(frozen=True, slots=True)
class SchemaHasUnresolvableReference:
    """A reference does not name a schema in the complete root schema.

    Attributes:
        reference: The `$ref` or `$dynamicRef` text that could not be resolved inside the root resource.
    """

    reference: str


@dataclass(frozen=True, slots=True)
class SchemaHasSameInstanceReferenceCycle:
    """A reference cycle applies forever to one instance without reaching a keyword.

    Attributes:
        reference: The last `$ref` or `$dynamicRef` on the cycle path, used to identify the schema link leading into it.
    """

    reference: str


type SchemaCheckFailure = (
    SchemaMetaError
    | SchemaHasIdentifier
    | SchemaUsesForeignDialect
    | SchemaHasUnresolvableReference
    | SchemaHasSameInstanceReferenceCycle
)
"""A reason the schema cannot be safely applied under the accepted dialect."""


def check_schema(schema: Mapping[str, Plain]) -> SchemaCheckFailure | None:
    """Check schema structure, resource boundaries and references without exposing library records.

    Args:
        schema: The complete root schema as plain JSON data.

    Returns:
        The first schema issue, in document order, or `None` when its structure and references are usable.
    """
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        return SchemaMetaError(exc.message)

    registry = Registry().with_resource('', DRAFT202012.create_resource(schema))
    for subschema in _iter_schemas_within(schema):
        if '$id' in subschema:
            return SchemaHasIdentifier()
        dialect = subschema.get('$schema', DIALECT)
        if not isinstance(dialect, str):
            # SAFETY: The meta-schema check above proves `$schema`, when present, is a string.
            raise Unreachable('the meta-schema proved `$schema` is a string')
        if dialect != DIALECT:
            return SchemaUsesForeignDialect(dialect)
        for keyword in ('$ref', '$dynamicRef'):
            reference = subschema.get(keyword)
            if reference is None:
                continue
            if not isinstance(reference, str):
                # SAFETY: The meta-schema check above proves each present reference keyword is a string.
                raise Unreachable(f'the meta-schema proved `{keyword}` is a string')
            if not _resolves_inside(registry, reference):
                return SchemaHasUnresolvableReference(reference)

    cycle = _same_instance_ref_cycle(registry, schema)
    if cycle is not None:
        return SchemaHasSameInstanceReferenceCycle(cycle)
    return None


def _resolves_inside(registry: Registry, reference: str) -> bool:
    """Whether a reference names a schema in the one resource held by `registry`.

    Args:
        registry: The complete root schema registered as one resource under the empty base URI.
        reference: The reference text to resolve; non-fragment references name resources outside that root.
    """
    if reference and not reference.startswith('#'):
        return False
    try:
        target = registry.resolver().lookup(reference).contents
    except Unresolvable:
        return False
    return isinstance(target, Mapping | bool)


# These applicators apply a subschema to the same instance as their own schema.
_SAME_INSTANCE_SINGLE: Final[tuple[str, ...]] = ('not', 'if', 'then', 'else')
_SAME_INSTANCE_LISTS: Final[tuple[str, ...]] = ('allOf', 'anyOf', 'oneOf')
_SAME_INSTANCE_MAPS: Final[tuple[str, ...]] = ('dependentSchemas',)


def _same_instance_ref_cycle(registry: Registry, schema: Mapping[str, Plain]) -> str | None:
    """The reference that closes an instance-preserving cycle, or `None` when none exists.

    Args:
        registry: The complete root schema registered as one resource, with its references already checked.
        schema: The complete plain root schema whose instance-preserving paths are searched for a cycle.
    """
    settled: set[int] = set()

    def visit(node: Mapping[str, Plain], on_path: set[int], last_reference: str) -> str | None:
        key = id(node)
        if key in settled:
            return None
        on_path.add(key)
        for target, reference in _same_instance_schemas(registry, node):
            via = reference if reference is not None else last_reference
            if id(target) in on_path:
                return via
            closing = visit(target, on_path, via)
            if closing is not None:
                return closing
        on_path.discard(key)
        settled.add(key)
        return None

    for subschema in _iter_schemas_within(schema):
        closing = visit(subschema, set(), '#')
        if closing is not None:
            return closing
    return None


def _same_instance_schemas(
    registry: Registry, node: Mapping[str, Plain]
) -> Iterator[tuple[Mapping[str, Plain], str | None]]:
    """Yield same-instance child schemas and the reference, if any, that leads to each.

    Args:
        registry: The complete root resource containing `node`; references have already been checked.
        node: An object subschema in that resource whose same-instance child schemas are yielded.

    Yields:
        Each child schema paired with its incoming reference, or `None` when reached through an applicator.
    """
    for keyword in ('$ref', '$dynamicRef'):
        reference = node.get(keyword)
        if isinstance(reference, str):
            target = registry.resolver().lookup(reference).contents
            if isinstance(target, Mapping):
                yield target, reference
    for keyword in _SAME_INSTANCE_SINGLE:
        sub = node.get(keyword)
        if isinstance(sub, Mapping):
            yield sub, None
    for keyword in _SAME_INSTANCE_LISTS:
        subs = node.get(keyword)
        if isinstance(subs, list):
            for sub in subs:
                if isinstance(sub, Mapping):
                    yield sub, None
    for keyword in _SAME_INSTANCE_MAPS:
        named = node.get(keyword)
        if isinstance(named, Mapping):
            for sub in named.values():
                if isinstance(sub, Mapping):
                    yield sub, None


def _iter_schemas_within(schema: Mapping[str, Plain]) -> Iterator[Mapping[str, Plain]]:
    """Yield root and object subschemas at the locations the accepted dialect defines.

    Args:
        schema: The complete root schema whose schema-valued locations are traversed.

    Yields:
        The root and each nested object subschema in dialect traversal order; boolean schemas are omitted.
    """
    yield schema
    for subschema in DRAFT202012.subresources_of(schema):
        if isinstance(subschema, Mapping):
            yield from _iter_schemas_within(subschema)
