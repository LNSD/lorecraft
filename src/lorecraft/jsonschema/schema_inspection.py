"""Inspect schema validity and the references the accepted dialect applies to one instance."""

from collections.abc import Mapping
from dataclasses import dataclass

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from lorecraft.core.error import Unreachable
from lorecraft.core.mapping import Plain

from . import find_same_instance_ref_cycle, is_resolved_inside, iter_schemas
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

    for subschema in iter_schemas(schema):
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
            if not is_resolved_inside(schema, reference):
                return SchemaHasUnresolvableReference(reference)

    cycle = find_same_instance_ref_cycle(schema)
    if cycle is not None:
        return SchemaHasSameInstanceReferenceCycle(cycle)
    return None
