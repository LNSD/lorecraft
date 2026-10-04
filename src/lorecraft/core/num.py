"""The number values: a whole number of at least 1, and one of at least 0.

`NonZeroUnsignedInt` is also a pydantic type, so a model field declared with it reads a JSON integer into one, writes it
back as the integer, and states its bound in the JSON Schema rendered from the model. A number it refuses is a
validation error carrying its own message.

A note on the pydantic hooks. pydantic reports only its own error types as a field's validation error; any other
exception escapes the model's validation whole, so the type rewraps its own rejection as a `PydanticCustomError`.
The message goes in the error's context rather than its template, with the template `'{reason}'`, so the
formatted `msg` is the message exactly.
"""

from dataclasses import dataclass
from typing import ClassVar, Final, Literal, Self

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import PydanticCustomError, core_schema

from lorecraft.core.error import Error

# The pydantic error type the value object raises its rejection under, typed as a literal because
# `PydanticCustomError` takes only a literal string.
_ERROR_TYPE: Final[Literal['non_zero_unsigned_int']] = 'non_zero_unsigned_int'


class NonPositiveIntError(Error):
    """A whole number is below 1.

    Attributes:
        value: The rejected number.
    """

    value: int

    def __init__(self, value: int) -> None:
        self.value = value
        super().__init__(f'must be at least {NonZeroUnsignedInt.MINIMUM}, got {value}')


@dataclass(frozen=True, slots=True)
class NonZeroUnsignedInt:
    """A whole number of at least 1.

    As a pydantic type it is read strictly: a JSON boolean, a number with a fraction or a string of digits is not
    one, even where Python would take it as one.

    Attributes:
        value: The validated number.
        MINIMUM: The smallest number the type holds, 1: the bound `__post_init__` checks and the JSON Schema states.
    """

    MINIMUM: ClassVar[int] = 1

    value: int

    @classmethod
    def parse(cls, raw: int) -> Self:
        """Return a validated number.

        Args:
            raw: Candidate number.

        Raises:
            NonPositiveIntError: If the number is below 1.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing the invariant.

        Raises:
            NonPositiveIntError: If the number is below 1.
        """
        if self.value < self.MINIMUM:
            raise NonPositiveIntError(self.value)

    def __str__(self) -> str:
        """The number in decimal digits."""
        return str(self.value)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: type[object], handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """How pydantic validates and serializes a field of this type: see the module's note.

        Args:
            source: The annotated type pydantic is building a schema for; unused.
            handler: Pydantic's schema generator; unused, because the schema is a plain validator function.
        """
        return core_schema.no_info_plain_validator_function(
            cls._from_pydantic, serialization=core_schema.plain_serializer_function_ser_schema(cls._to_pydantic)
        )

    @classmethod
    def _from_pydantic(cls, value: object) -> Self:
        """Take a `NonZeroUnsignedInt` as it is and parse an integer into one; anything else raises pydantic's error.

        Args:
            value: The input pydantic holds for the field: an instance, an integer, or anything else.

        Raises:
            PydanticCustomError: If the value is not an integer (type `int_type`), or is below 1 (type
                `non_zero_unsigned_int`).
        """
        if isinstance(value, cls):
            return value
        # A `bool` is an `int` to Python, but `true` in a JSON document is not a number.
        if isinstance(value, bool) or not isinstance(value, int):
            raise PydanticCustomError('int_type', 'Input should be a valid integer')
        try:
            return cls.parse(value)
        except NonPositiveIntError as exc:
            raise PydanticCustomError(_ERROR_TYPE, '{reason}', {'reason': str(exc)}) from exc

    def _to_pydantic(self) -> int:
        """The integer pydantic serializes a field of this type to."""
        return self.value

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """The JSON Schema of a field of this type: the rule `__post_init__` checks.

        Args:
            schema: The core schema pydantic built for the field; unused, because the JSON Schema is fixed.
            handler: Pydantic's JSON Schema generator; unused for the same reason.
        """
        return {'type': 'integer', 'minimum': cls.MINIMUM}


class NegativeIntError(Error):
    """A whole number is below 0.

    Attributes:
        value: The rejected number.
    """

    value: int

    def __init__(self, value: int) -> None:
        self.value = value
        super().__init__(f'must be at least {UnsignedInt.MINIMUM}, got {value}')


@dataclass(frozen=True, slots=True)
class UnsignedInt:
    """A whole number of at least 0.

    No model field holds one yet, so it has no pydantic hooks; they go on the type, as `NonZeroUnsignedInt`'s do,
    when one does.

    Attributes:
        value: The validated number.
        MINIMUM: The smallest number the type holds, 0: the bound `__post_init__` checks.
    """

    MINIMUM: ClassVar[int] = 0

    value: int

    @classmethod
    def parse(cls, raw: int) -> Self:
        """Return a validated number.

        Args:
            raw: Candidate number.

        Raises:
            NegativeIntError: If the number is below 0.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing the invariant.

        Raises:
            NegativeIntError: If the number is below 0.
        """
        if self.value < self.MINIMUM:
            raise NegativeIntError(self.value)

    def __str__(self) -> str:
        """The number in decimal digits."""
        return str(self.value)
