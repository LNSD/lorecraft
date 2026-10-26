"""Project-independent details read from a JSON Schema validation failure."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import NewType

from lorecraft.core.mapping import Frozen, FrozenMapping, Plain

from .schema_keyword import Keyword

InstancePath = NewType('InstancePath', tuple[str | int, ...])
"""The path through the instance to the value a violation concerns."""

SchemaPath = NewType('SchemaPath', tuple[str | int, ...])
"""The path through the schema to the keyword that failed."""


@dataclass(frozen=True, slots=True)
class MissingRequiredProperties:
    """A required property name absent from the object that failed validation."""

    field: str


@dataclass(frozen=True, slots=True)
class DependentProperty:
    """One written property and one required property missing because of it."""

    field: str
    missing: str


@dataclass(frozen=True, slots=True)
class MissingDependentProperties:
    """A missing dependency of a dependent property written in the instance."""

    dependency: DependentProperty


@dataclass(frozen=True, slots=True)
class AdditionalProperties:
    """The instance properties refused by `additionalProperties`."""

    fields: tuple[str, ...]

    def __post_init__(self) -> None:
        """Refuse the impossible case where no additional property was rejected.

        Raises:
            ValueError: If there is no rejected field.
        """
        if not self.fields:
            raise ValueError('additionalProperties must reject at least one field')


@dataclass(frozen=True, slots=True)
class UnevaluatedProperties:
    """The instance properties refused by `unevaluatedProperties`."""

    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InvalidPropertyName:
    """A property name rejected by the schema's `propertyNames` subschema."""

    name: str


type ViolationFact = (
    MissingRequiredProperties
    | MissingDependentProperties
    | AdditionalProperties
    | UnevaluatedProperties
    | InvalidPropertyName
)


@dataclass(frozen=True, slots=True)
class Violation:
    """A validator failure without any validator-library records.

    Attributes:
        message: The validator's wording, retained verbatim.
        keyword: The typed keyword that failed.
        path: The instance path to the failing value.
        schema_path: The schema path to the failing keyword.
        instance: The plain value the failure concerns.
        schema: The schema object containing the failed keyword.
        evaluated_properties: Properties evaluated by this schema, needed to interpret
            `unevaluatedProperties` failures.
        facts: Typed, keyword-specific details about the object or property name that failed validation.
    """

    message: str
    keyword: Keyword
    path: InstancePath
    schema_path: SchemaPath
    instance: Frozen
    schema: Frozen
    evaluated_properties: frozenset[str]
    facts: tuple[ViolationFact, ...] = ()


def _freeze(value: Plain) -> Frozen:
    """Copy a plain JSON value into immutable Lorecraft containers."""
    if isinstance(value, Mapping):
        return FrozenMapping.from_plain(value)
    if isinstance(value, Sequence) and not isinstance(value, str):
        return tuple(_freeze(item) for item in value)
    return value
