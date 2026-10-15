"""Project-independent facts read from a JSON Schema validation failure."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from lorecraft.core.mapping import Frozen, FrozenMapping, Plain

from .schema_keyword import Keyword


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
    """

    message: str
    keyword: Keyword
    path: tuple[str | int, ...]
    schema_path: tuple[str | int, ...]
    instance: Frozen
    schema: Frozen
    evaluated_properties: frozenset[str]

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
