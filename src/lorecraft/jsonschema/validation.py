"""The one adapter from JSON Schema validator records to Lorecraft values."""

from collections.abc import Mapping
from dataclasses import dataclass

from jsonschema import Draft202012Validator
from jsonschema._utils import find_evaluated_property_keys_by_schema
from jsonschema.exceptions import ValidationError, best_match
from jsonschema.protocols import Validator as SchemaValidator

from lorecraft.core.mapping import Plain

from .schema_inspection import SchemaCheckFailure, check_schema
from .schema_keyword import keyword_of
from .violation import Violation, _freeze


def validate(schema: Mapping[str, Plain], instance: Plain) -> tuple[Violation, ...]:
    """Validate a plain JSON value and return ordered, library-independent failures.

    Args:
        schema: The schema to validate against.
        instance: The plain JSON value to validate.

    Returns:
        The failures, ordered by instance path and then message. Each violation contains the schema and instance
        context and evaluated-property facts needed to interpret the failure without validator-library records.
    """
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


@dataclass(frozen=True, slots=True, init=False)
class CheckedSchema:
    """A schema that passed `check_schema`, ready to validate plain JSON instances.

    Build one with `CheckedSchema.check`; validating against a schema that failed the check could raise library
    exceptions, so there is no other constructor.
    """

    schema: Mapping[str, Plain]

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Refuse direct construction, which would skip the schema check."""
        raise TypeError('build a CheckedSchema with CheckedSchema.check(schema)')

    @classmethod
    def check(cls, schema: Mapping[str, Plain]) -> 'CheckedSchema | SchemaCheckFailure':
        """Return the schema ready to validate, or the first reason `check_schema` refuses it."""
        failure = check_schema(schema)
        if failure is not None:
            return failure
        checked = object.__new__(cls)
        object.__setattr__(checked, 'schema', schema)
        return checked

    def validate(self, instance: Plain) -> tuple[Violation, ...]:
        """Return every failure ordered by instance path and message, without raising for invalid data.

        Paths compare segment by segment as text, so array index 10 sorts before 2. Failures with the same path and
        message are reported once.
        """
        violations = validate(self.schema, instance)
        ordered: list[Violation] = []
        seen: set[tuple[tuple[str | int, ...], str]] = set()
        for violation in violations:
            identity = (violation.path, violation.message)
            if identity not in seen:
                seen.add(identity)
                ordered.append(violation)
        return tuple(ordered)
