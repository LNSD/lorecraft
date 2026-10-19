"""Project-independent details read from a JSON Schema validation failure."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from lorecraft.core.mapping import Frozen, FrozenMapping, Plain

from .schema_keyword import Keyword


@dataclass(frozen=True, slots=True)
class MissingRequiredProperties:
    """The required property names absent from the object that failed validation."""

    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DependentProperty:
    """One written property and one required property missing because of it."""

    field: str
    missing: str


@dataclass(frozen=True, slots=True)
class MissingDependentProperties:
    """The missing dependencies for the dependent properties written in the instance."""

    dependencies: tuple[DependentProperty, ...]


@dataclass(frozen=True, slots=True)
class AdditionalProperties:
    """The instance properties refused by `additionalProperties`."""

    fields: tuple[str, ...]


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
    path: tuple[str | int, ...]
    schema_path: tuple[str | int, ...]
    instance: Frozen
    schema: Frozen
    evaluated_properties: frozenset[str]
    facts: tuple[ViolationFact, ...] = ()

    def __post_init__(self) -> None:
        """Copy plain containers into deeply immutable values."""
        object.__setattr__(self, 'instance', _freeze(self.instance))
        object.__setattr__(self, 'schema', _freeze(self.schema))


def _freeze(value: Plain) -> Frozen:
    """Copy a plain JSON value into immutable Lorecraft containers."""
    if isinstance(value, Mapping):
        return FrozenMapping.from_plain(value)
    if isinstance(value, Sequence) and not isinstance(value, str):
        return tuple(_freeze(item) for item in value)
    return value
