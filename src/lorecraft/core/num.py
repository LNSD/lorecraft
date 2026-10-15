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

from .error import Error

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


@dataclass(frozen=True, slots=True, order=True)
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

    def __post_init__(self) -> None:
        """Refuse a number below `MINIMUM`.

        Raises:
            NonPositiveIntError: If the number is below 1.
        """
        if self.value < self.MINIMUM:
            raise NonPositiveIntError(self.value)

    def __str__(self) -> str:
        """The number in decimal digits."""
        return str(self.value)

    def __format__(self, format_spec: str) -> str:
        """The number in decimal digits, formatted as an integer is: `f'{number:>3}'` pads it to 3 columns."""
        return format(self.value, format_spec)

    def as_unsigned(self) -> 'UnsignedInt':
        """The same number as an `UnsignedInt`, to compare or combine it with one."""
        return UnsignedInt(self.value)

    def successor(self) -> 'NonZeroUnsignedInt':
        """The number one above this one."""
        return NonZeroUnsignedInt(self.value + 1)

    def between(self, earlier: 'NonZeroUnsignedInt') -> 'UnsignedInt':
        """How many whole numbers lie strictly between `earlier` and this number: 0 for two that are adjacent.

        Args:
            earlier: The lower end, which this number is above.

        Raises:
            NegativeIntError: If this number is not above `earlier`.
        """
        return UnsignedInt(self.value - earlier.value - 1)

    def position(self) -> int:
        """Where this number's element sits in a sequence counted from 1 but held from 0: 0 for 1.

        This is the one exit to a bare integer, for indexing the sequence; a number that is written out is
        formatted instead.
        """
        return self.value - 1

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
        """Take a `NonZeroUnsignedInt` as it is and build one from an integer; anything else raises pydantic's error.

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
            return cls(value)
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


@dataclass(frozen=True, slots=True, order=True)
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

    def __post_init__(self) -> None:
        """Refuse a number below `MINIMUM`.

        Raises:
            NegativeIntError: If the number is below 0.
        """
        if self.value < self.MINIMUM:
            raise NegativeIntError(self.value)

    def __str__(self) -> str:
        """The number in decimal digits."""
        return str(self.value)

    def __format__(self, format_spec: str) -> str:
        """The number in decimal digits, formatted as an integer is: `f'{number:>3}'` pads it to 3 columns."""
        return format(self.value, format_spec)

    def __add__(self, other: 'UnsignedInt') -> 'UnsignedInt':
        """The sum of two numbers, which is again a number of at least 0."""
        return UnsignedInt(self.value + other.value)

    def exceeds(self, cap: NonZeroUnsignedInt) -> bool:
        """Whether this number is past `cap`; a number equal to the cap is within it.

        Args:
            cap: The most the number may reach.
        """
        return self > cap.as_unsigned()

    def excess_over(self, cap: NonZeroUnsignedInt) -> NonZeroUnsignedInt:
        """How far this number runs past `cap`.

        Args:
            cap: The most the number may reach.

        Raises:
            NonPositiveIntError: If the number does not exceed `cap`, so there is no excess.
        """
        return NonZeroUnsignedInt(self.value - cap.as_unsigned().value)

    def minus(self, other: NonZeroUnsignedInt) -> 'UnsignedInt | None':
        """The number left after taking `other` away, or `None` when `other` is more than this number holds.

        Args:
            other: The amount to take away.
        """
        taken = other.as_unsigned()
        if self < taken:
            return None
        return UnsignedInt(self.value - taken.value)

    def or_one(self) -> NonZeroUnsignedInt:
        """The number itself, or 1 when it is 0: the nearest number of at least 1."""
        if self == UnsignedInt(0):
            return NonZeroUnsignedInt(1)
        return NonZeroUnsignedInt(self.value)

    def successor(self) -> NonZeroUnsignedInt:
        """The number one above this one, which is at least 1."""
        return NonZeroUnsignedInt(self.value + 1)
