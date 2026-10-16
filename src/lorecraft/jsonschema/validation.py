"""The one adapter from JSON Schema validator records to Lorecraft values."""

from collections.abc import Mapping

from jsonschema import Draft202012Validator
from jsonschema._utils import find_evaluated_property_keys_by_schema
from jsonschema.exceptions import ValidationError, best_match
from jsonschema.protocols import Validator as SchemaValidator

from lorecraft.core.mapping import Plain

from .schema_keyword import keyword_of
from .violation import Violation, _freeze


def validate(schema: Mapping[str, Plain], instance: Plain) -> tuple[Violation, ...]:
    """Validate plain JSON values and return ordered, library-independent failures."""
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(instance),
        key=lambda error: (tuple(str(part) for part in error.path), error.message),
    )
    return tuple(_violation(validator, error) for error in errors)


def best_violation(
    schema: Mapping[str, Plain], instance: Plain, *, root_schema: Mapping[str, Plain] | None = None
) -> Violation | None:
    """Return the best failure, resolving a subschema against its root when one is supplied.

    Args:
        schema: The schema or subschema to validate against.
        instance: The plain JSON value to validate.
        root_schema: The enclosing root schema for resolving local references in `schema`, or `None`
            when `schema` is already the root.
    """
    validator = Draft202012Validator(schema if root_schema is None else root_schema)
    if root_schema is not None:
        validator = validator.evolve(schema=schema)
    # `best_match` preserves jsonschema's selection policy for nested constraints.
    error = best_match(validator.iter_errors(instance))
    return None if error is None else _violation(validator, error)


def _violation(validator: SchemaValidator, error: ValidationError) -> Violation:
    schema: Plain = error.schema
    evaluated = frozenset()
    if isinstance(error.instance, Mapping):
        scoped_validator = validator.evolve(schema=schema)
        evaluated = frozenset(find_evaluated_property_keys_by_schema(scoped_validator, error.instance, schema))
    return Violation(
        error.message,
        keyword_of(error),
        tuple(error.path),
        tuple(error.relative_schema_path),
        _freeze(error.instance),
        _freeze(schema),
        evaluated,
    )
