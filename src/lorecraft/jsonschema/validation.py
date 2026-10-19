"""The one adapter from JSON Schema validator records to Lorecraft values."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from jsonschema import Draft202012Validator
from jsonschema._utils import find_evaluated_property_keys_by_schema
from jsonschema.exceptions import ValidationError, best_match
from jsonschema.protocols import Validator as SchemaValidator

from lorecraft.core.mapping import Plain

from .messages import dependency_message, required_message
from .schema_inspection import SchemaCheckFailure, check_schema
from .schema_keyword import (
    AdditionalPropertiesKeyword,
    DependentRequiredKeyword,
    Keyword,
    RequiredKeyword,
    UnevaluatedPropertiesKeyword,
    keyword_of,
)
from .violation import (
    AdditionalProperties,
    DependentProperty,
    InvalidPropertyName,
    MissingDependentProperties,
    MissingRequiredProperties,
    UnevaluatedProperties,
    Violation,
    ViolationFact,
    _freeze,
)


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
    return tuple(_violation(validator, error, instance) for error in errors)


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
    return None if error is None else _violation(validator, error, instance)


def _violation(validator: SchemaValidator, error: ValidationError, root_instance: Plain) -> Violation:
    schema: Plain = error.schema
    evaluated = frozenset()
    if isinstance(error.instance, Mapping):
        scoped_validator = validator.evolve(schema=schema)
        evaluated = frozenset(find_evaluated_property_keys_by_schema(scoped_validator, error.instance, schema))
    keyword = keyword_of(error)
    return Violation(
        error.message,
        keyword,
        tuple(error.path),
        tuple(error.relative_schema_path),
        _freeze(error.instance),
        _freeze(schema),
        evaluated,
        _facts(error, keyword, evaluated, root_instance),
    )


def _facts(
    error: ValidationError, keyword: Keyword, evaluated: frozenset[str], root_instance: Plain
) -> tuple[ViolationFact, ...]:
    """Return the typed facts of an object-keyword failure, each narrowed to what this one violation is about."""
    if _is_property_name_failure(error, root_instance):
        return (InvalidPropertyName(str(error.instance)),)
    schema, instance = error.schema, error.instance
    if not isinstance(schema, Mapping) or not isinstance(instance, Mapping):
        return ()
    match keyword:
        case RequiredKeyword(fields):
            # `jsonschema` reports one violation per missing field, worded for that field alone.
            return tuple(
                MissingRequiredProperties((field,))
                for field in fields
                if field not in instance and required_message(field) == error.message
            )
        case DependentRequiredKeyword(dependencies):
            return tuple(
                MissingDependentProperties((DependentProperty(field, dependency),))
                for field, needs in dependencies
                if field in instance
                for dependency in needs
                if dependency not in instance and dependency_message(field, dependency) == error.message
            )
        case AdditionalPropertiesKeyword():
            properties = schema.get('properties', {})
            patterns = schema.get('patternProperties', {})
            if not isinstance(properties, Mapping) or not isinstance(patterns, Mapping):
                return ()
            rejected = tuple(
                key
                for key in instance
                if key not in properties and not any(re.search(str(pattern), key) for pattern in patterns)
            )
            return (AdditionalProperties(rejected),)
        case UnevaluatedPropertiesKeyword():
            return (UnevaluatedProperties(tuple(key for key in instance if key not in evaluated)),)
        case _:
            return ()


def _is_property_name_failure(error: ValidationError, root_instance: Plain) -> bool:
    """Whether the failure is about a key of the value at its path, which only `propertyNames` reports.

    Every other failure has the value at its path as its instance, so the keyword tables and the `$ref`, `prefixItems`
    and `contentSchema` hops between schemas never need walking.
    """
    value: object = root_instance
    for part in error.absolute_path:
        if isinstance(value, Mapping) and isinstance(part, str):
            value = value.get(part)
        elif isinstance(value, list) and isinstance(part, int):
            value = value[part]
        else:
            return False
    return value is not error.instance


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
    def check(cls, schema: Mapping[str, Plain]) -> CheckedSchema | SchemaCheckFailure:
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
