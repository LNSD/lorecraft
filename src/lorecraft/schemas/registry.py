"""Pure in-memory lookup for schema inputs supplied by the loaded model."""

from dataclasses import dataclass
from typing import Self

from lorecraft.core.error import Error

from .types import SchemaInput, SchemaReference


class SchemaReferenceError(Error):
    """A reference is absent from a schema registry.

    Attributes:
        reference: The requested identity.
    """

    reference: SchemaReference

    def __init__(self, reference: SchemaReference) -> None:
        self.reference = reference
        super().__init__(f'no schema is registered for {reference.kind.value}:{reference.identity}')


class DuplicateSchemaReferenceError(Error):
    """Two inputs claim the same schema identity.

    Attributes:
        reference: The duplicated identity.
    """

    reference: SchemaReference

    def __init__(self, reference: SchemaReference) -> None:
        self.reference = reference
        super().__init__(f'schema reference {reference.kind.value}:{reference.identity} is registered more than once')


@dataclass(frozen=True, slots=True)
class SchemaRegistry:
    """An immutable registry whose resolution performs no I/O or external resource lookup.

    Attributes:
        inputs: Unique schema inputs supplied by the loaded model.
    """

    inputs: tuple[SchemaInput, ...]

    def __post_init__(self) -> None:
        """Reject ambiguous registry identities."""
        seen: set[SchemaReference] = set()
        for schema_input in self.inputs:
            if schema_input.reference in seen:
                raise DuplicateSchemaReferenceError(schema_input.reference)
            seen.add(schema_input.reference)

    @classmethod
    def from_inputs(cls, inputs: tuple[SchemaInput, ...]) -> Self:
        """Build a registry from the immutable inputs already present in a loaded model."""
        return cls(inputs)

    def resolve(self, reference: SchemaReference) -> SchemaInput:
        """Return the input for `reference`, or raise when the loaded model has no such input."""
        for schema_input in self.inputs:
            if schema_input.reference == reference:
                return schema_input
        raise SchemaReferenceError(reference)
