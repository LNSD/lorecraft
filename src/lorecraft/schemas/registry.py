"""Pure in-memory lookup for schema inputs supplied by the loaded model."""

from dataclasses import dataclass
from typing import Self

from lorecraft.core.error import Error
from lorecraft.core.mapping import FrozenMapping

from .types import SchemaInput, SchemaRef


class SchemaRefError(Error):
    """A reference is absent from a schema registry.

    Attributes:
        reference: The requested identity.
    """

    reference: SchemaRef

    def __init__(self, reference: SchemaRef) -> None:
        self.reference = reference
        super().__init__(f'no schema is registered for {reference.kind.value}:{reference.identity}')


class DuplicateSchemaRefError(Error):
    """Two inputs claim the same schema identity.

    Attributes:
        reference: The duplicated identity.
    """

    reference: SchemaRef

    def __init__(self, reference: SchemaRef) -> None:
        self.reference = reference
        super().__init__(f'schema reference {reference.kind.value}:{reference.identity} is registered more than once')


@dataclass(frozen=True, slots=True)
class SchemaRegistry:
    """An immutable registry whose resolution performs no I/O or external resource lookup.

    Attributes:
        inputs: Unique schema inputs supplied by the loaded model, keyed by typed reference.
    """

    inputs: FrozenMapping[SchemaRef, SchemaInput]

    @classmethod
    def from_inputs(cls, inputs: tuple[SchemaInput, ...]) -> Self:
        """Build a registry from loaded inputs, refusing a repeated typed identity."""
        by_reference: dict[SchemaRef, SchemaInput] = {}
        for schema_input in inputs:
            reference = schema_input.reference
            if reference in by_reference:
                raise DuplicateSchemaRefError(reference)
            by_reference[reference] = schema_input
        return cls(FrozenMapping(by_reference))

    def resolve(self, reference: SchemaRef) -> SchemaInput:
        """Return the input for `reference`, or raise when the loaded model has no such input."""
        schema_input = self.inputs.get(reference)
        if schema_input is None:
            raise SchemaRefError(reference)
        return schema_input
