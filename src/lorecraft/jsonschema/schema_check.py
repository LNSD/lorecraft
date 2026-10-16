"""Same-instance reference analysis over plain JSON Schema data."""

from collections.abc import Iterator, Mapping
from typing import Final

from referencing import Registry
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012

from lorecraft.core.mapping import Plain


def is_resolved_inside(schema: Mapping[str, Plain], ref: str) -> bool:
    """Whether a `$ref` or `$dynamicRef` resolves to a schema inside this single resource.

    Only a reference that is empty or opens with `#` can: any other names another resource, which is never fetched,
    so it is refused without being looked up. What it names must be a schema, an object or a boolean, as `jsonschema`
    raises when it reads anything else, such as `#/required/0`, as one.

    Args:
        schema: The whole single-resource schema as plain data (`dict` and `list`), registered under the empty
            base URI.
        ref: The `$ref` or `$dynamicRef` target string as written; the empty reference is the schema itself, as
            `#` is.
    """
    if ref and not ref.startswith('#'):
        return False
    registry = Registry().with_resource('', DRAFT202012.create_resource(schema))
    try:
        target = registry.resolver().lookup(ref).contents
    except Unresolvable:
        return False
    return isinstance(target, Mapping | bool)


_SAME_INSTANCE_SINGLE: Final[tuple[str, ...]] = ('not', 'if', 'then', 'else')
_SAME_INSTANCE_LISTS: Final[tuple[str, ...]] = ('allOf', 'anyOf', 'oneOf')
_SAME_INSTANCE_MAPS: Final[tuple[str, ...]] = ('dependentSchemas',)


def find_same_instance_ref_cycle(schema: Mapping[str, Plain]) -> str | None:
    """Find a local reference cycle that can repeat without consuming an instance.

    A reference moves to its target without reading any of the instance, as do `allOf`, `anyOf`, `oneOf`, `not`,
    `if`, `then`, `else` and `dependentSchemas`. Following only those from every schema, a path that returns to a
    schema it left never reaches a keyword that reads the value, so validating would recurse without end if the
    path were applied. Every schema is walked, used or not: a cycle nothing refers to is still a defect in the
    schema. A reference below `properties` or `items` is not followed: it applies to a smaller value, so a
    recursive schema such as a tree is fine.

    Args:
        schema: The whole single-resource schema as plain data (`dict` and `list`), every reference of which
            already resolves inside it.

    Returns:
        The `$ref` or `$dynamicRef` string that closes a same-instance cycle (or `'#'` when the cycle closes
        without crossing a reference), or `None` when the schema contains no such cycle.
    """
    registry = Registry().with_resource('', DRAFT202012.create_resource(schema))
    settled: set[int] = set()

    def visit(node: Mapping[str, Plain], on_path: set[int], last_ref: str) -> str | None:
        key = id(node)
        if key in settled:
            return None
        on_path.add(key)
        # Structural children consume the instance and are not cycle edges; only the keywords below can recur
        # against the same instance and make evaluation non-terminating.
        for target, ref in _same_instance_schemas(registry, node):
            via = ref if ref is not None else last_ref
            if id(target) in on_path:
                return via
            closing = visit(target, on_path, via)
            if closing is not None:
                return closing
        on_path.discard(key)
        settled.add(key)
        return None

    for subschema in iter_schemas(schema):
        closing = visit(subschema, set(), '#')
        if closing is not None:
            return closing
    return None


def _same_instance_schemas(
    registry: Registry, node: Mapping[str, Plain]
) -> Iterator[tuple[Mapping[str, Plain], str | None]]:
    """Yield edges that re-evaluate this instance; structural recursion consumes it and is safe.

    Args:
        registry: A registry holding the single-resource schema `node` belongs to, under the empty base URI,
            every reference of which resolves.
        node: One object schema as plain data (`dict` and `list`).

    Yields:
        `(target, ref)` for each object subschema `node` applies to the same instance, paired with the `$ref`
        or `$dynamicRef` string that led to it, or `None` when reached directly through a combinator keyword.
    """
    for keyword in ('$ref', '$dynamicRef'):
        ref = node.get(keyword)
        if isinstance(ref, str):
            target = registry.resolver().lookup(ref).contents
            if isinstance(target, Mapping):
                yield target, ref
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


def iter_schemas(schema: Mapping[str, Plain]) -> Iterator[Mapping[str, Plain]]:
    """Walk JSON Schema locations using the validator's plain dict/list representation.

    Only the places Draft 2020-12 reads a schema from are walked, such as `properties` or `items`, so a value
    under `enum` or `const` that happens to hold `$id` is payload data, not a schema, and is excluded. A boolean
    subschema holds no keyword, so it is skipped.

    Args:
        schema: The single-resource root schema to walk, as plain data (`dict` and `list`).

    Yields:
        `schema` first, then each object subschema inside it at any depth, skipping boolean schemas and excluding
        `enum` and `const` payload data.
    """
    yield schema
    for subschema in DRAFT202012.subresources_of(schema):
        if isinstance(subschema, Mapping):
            yield from iter_schemas(subschema)
