"""A section name: the heading text a structure specification names a section by.

An outline entry names the section it places, and `forbidden` lists the sections that must not appear, both by the
text of the section's H2 heading. A heading's text never carries whitespace at either end, since Markdown strips it
before the heading is read, and never a line break, which ends the heading. So a name that is empty, padded or more
than one line could match no heading written normally. Such a name is refused when the specification is loaded,
rather than reported against every document it governs.

`SectionName` is also a pydantic type, so a model field declared with it reads a JSON string into one, writes it
back as the string, and states its rule in the JSON Schema rendered from the model. A name it refuses is a
validation error carrying its own message.

A note on the pydantic hooks. pydantic reports only its own error types as a field's validation error; any other
exception escapes the model's validation whole, so the type rewraps its own rejection as a `PydanticCustomError`.
The message goes in the error's context rather than its template, because pydantic formats the template and a
rejected name may hold braces. The template is `'{reason}'`, so the formatted `msg` is the message exactly.
"""

from dataclasses import dataclass
from typing import ClassVar, Final, Literal, Self

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import PydanticCustomError, core_schema

from lorecraft.core.error import Error

# The pydantic error type the value object raises its rejection under, typed as a literal because
# `PydanticCustomError` takes only a literal string.
_ERROR_TYPE: Final[Literal['section_name']] = 'section_name'


class EmptySectionNameError(Error):
    """A section name is empty."""

    def __init__(self) -> None:
        super().__init__('must not be empty')


class PaddedSectionNameError(Error):
    """A section name starts or ends with whitespace.

    Attributes:
        name: The rejected name, exactly as supplied.
    """

    name: str

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f'must start and end with a non-whitespace character, got {name!r}')


class MultilineSectionNameError(Error):
    """A section name holds a line break inside it.

    Attributes:
        name: The rejected name, exactly as supplied.
    """

    name: str

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f'must be one line, got {name!r}')


@dataclass(frozen=True, slots=True)
class SectionName:
    """A section's heading text, without its `#` markers or inline markup.

    A valid name:

    - Is not empty.
    - Starts and ends with a character other than whitespace.
    - Is one line: it holds none of the line breaks `str.splitlines` splits on, the ones the Markdown parser ends a
      heading at.

    Whitespace inside the name is kept, and parsing preserves the spelling: a name matches a heading whose text is
    exactly the same.

    As a pydantic type it is read strictly: only a JSON string is a name.

    Attributes:
        value: The validated name, exactly as supplied.
        PATTERN: The regular expression the JSON Schema states the rule with, which an editor reads in the ECMA
            dialect. There `.` stops at a line feed, a carriage return, a line separator and a paragraph separator,
            so an editor misses the rarer breaks `str.splitlines` knows, such as a form feed; only the load refuses
            those.
    """

    PATTERN: ClassVar[str] = r'^\S(.*\S)?$'

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated section name.

        Args:
            raw: Candidate name.

        Raises:
            EmptySectionNameError: If the name is empty.
            PaddedSectionNameError: If the name starts or ends with whitespace.
            MultilineSectionNameError: If the name holds a line break inside it.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing the invariant.

        Raises:
            EmptySectionNameError: If the name is empty.
            PaddedSectionNameError: If the name starts or ends with whitespace.
            MultilineSectionNameError: If the name holds a line break inside it.
        """
        if not self.value:
            raise EmptySectionNameError()
        if self.value != self.value.strip():
            raise PaddedSectionNameError(self.value)
        # Every line break is whitespace, so one at either end was refused just above; more than one line here
        # means a break inside the name.
        if len(self.value.splitlines()) > 1:
            raise MultilineSectionNameError(self.value)

    def __str__(self) -> str:
        """The name, exactly as supplied."""
        return self.value

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
        """Take a `SectionName` as it is and parse a string into one; anything else raises pydantic's error.

        Args:
            value: The input pydantic holds for the field: an instance, a string, or anything else.

        Raises:
            PydanticCustomError: If the value is not a string (type `string_type`), or is not a valid name (type
                `section_name`).
        """
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise PydanticCustomError('string_type', 'Input should be a valid string')
        try:
            return cls.parse(value)
        except (EmptySectionNameError, PaddedSectionNameError, MultilineSectionNameError) as exc:
            raise PydanticCustomError(_ERROR_TYPE, '{reason}', {'reason': str(exc)}) from exc

    def _to_pydantic(self) -> str:
        """The string pydantic serializes a field of this type to."""
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
        return {'type': 'string', 'minLength': 1, 'pattern': cls.PATTERN}
