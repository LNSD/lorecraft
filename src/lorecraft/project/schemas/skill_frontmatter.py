"""The frontmatter of a skill's ``SKILL.md``, as the Agent Skills specification defines it.

This is the one declaration of its fields.

The specification is https://agentskills.io/specification. ``SkillFrontmatter`` states its six fields and the
limits it puts on them, and nothing else: an extension some agent reads beyond them, such as Claude Code's
``argument-hint``, is not a field here. ``SkillFrontmatterSchema`` holds a document's frontmatter to it, so a
skill that passes has this shape exactly. And ``just gen`` renders it into
``docs/schemas/skill-frontmatter.spec.json``, the JSON Schema an editor validates the frontmatter against while it
is written, so the editor and the check hold a skill to the same declaration.

Unlike a header specification, whose JSON Schema is written by hand and applied with the ``jsonschema`` package,
this schema is fixed by the specification, so it is declared once here as a pydantic model: pydantic validates a
skill against it, and the JSON Schema is rendered from it rather than read.

Each string field — the name, the description, the license, the compatibility note and the allowed tools — is a
value object of its own type: constructing one proves the text satisfies the specification, so code holding one
never checks it again. Each type stands alone, with its own errors and its own rules; none shares code with
another, so a rule changes in one place and touches no other field. A type's rules are declared once, as a pydantic
``TypeAdapter`` over a constrained ``str``: ``__post_init__`` runs it and turns the rule it reports broken into the
type's own error, and the type's JSON Schema is the adapter's, so the check and the schema cannot disagree. Every
value object is also a pydantic type: a field annotated with one takes an instance as it is and parses a string
into one, a string it refuses is a validation error carrying its own message, and serializing gives the string back.

The model is strict, frozen and closed. Strict, so a YAML value is never coerced into another type: an unquoted
``version: 1.0`` under ``metadata`` is a float, not the string the specification asks for. Frozen, so a parsed
frontmatter cannot change after it was validated. Closed (``extra='forbid'``), so a misspelt field is an error
rather than a field silently ignored. An optional field written with no value decodes to YAML's null, and reads
as absent.

What the schema shows an editor is declared here too: each field's docstring is its description, ``Field`` adds
its examples, taken from the specification, and the model's config names it and gives the specification's two
whole examples. What no field can state, such as ``name`` matching the skill's directory, is left to whoever
knows the directory.

A note on the pydantic hooks every value object carries. pydantic reports only its own error types as a field's
validation error; any other exception escapes the model's validation whole, so each type rewraps its own rejection
as a ``PydanticCustomError``. The message goes in the error's context rather than its template, because pydantic
formats the template and a rejected text may hold braces. The template is ``'{reason}'``, so the formatted ``msg``
is the message exactly, and it is read back from there, typed, rather than from the untyped context.
"""

from dataclasses import dataclass
from typing import Annotated, Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    StringConstraints,
    TypeAdapter,
    ValidationError,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import ErrorDetails, PydanticCustomError, core_schema

from lorecraft.core.error import Error

# The pydantic error type each value object raises its rejection under, typed as literals because
# `PydanticCustomError` takes only a literal string. `find_value_object_message` reads them back.
_NAME_ERROR_TYPE: Final[Literal['skill_name']] = 'skill_name'
_DESCRIPTION_ERROR_TYPE: Final[Literal['skill_description']] = 'skill_description'
_COMPATIBILITY_ERROR_TYPE: Final[Literal['skill_compatibility']] = 'skill_compatibility'


def find_value_object_message(detail: ErrorDetails) -> str | None:
    """The message a value object rejected a field's value with, or `None` when `detail` is not such an error.

    The message is the error's formatted `msg`: see the note on the pydantic hooks above.

    Args:
        detail: One entry of a pydantic `ValidationError`; only the three value-object error types yield a message.
    """
    if detail['type'] not in (_NAME_ERROR_TYPE, _DESCRIPTION_ERROR_TYPE, _COMPATIBILITY_ERROR_TYPE):
        return None
    return detail['msg']


SKILL_NAME_MAX_LENGTH: Final[int] = 64
"""The most characters a skill name may have."""

SKILL_NAME_PATTERN: Final[str] = r'^[a-z0-9]+(-[a-z0-9]+)*$'
"""Lowercase ASCII letters and digits in runs joined by single hyphens: no leading, trailing or doubled hyphen."""

_SKILL_NAME_RULES: Final[TypeAdapter[str]] = TypeAdapter(
    Annotated[str, StringConstraints(min_length=1, max_length=SKILL_NAME_MAX_LENGTH, pattern=SKILL_NAME_PATTERN)]
)
"""A skill name's rules, declared once: ``SkillName`` checks them and renders its JSON Schema from them."""


class EmptySkillNameError(Error):
    """A skill name is empty.

    Attributes:
        source: The rule the name broke, as pydantic reported it.
    """

    source: ValidationError

    def __init__(self, *, source: ValidationError) -> None:
        self.source = source
        super().__init__('skill name cannot be empty')
        self.__cause__ = source


class OverlongSkillNameError(Error):
    """A skill name has more characters than the specification allows.

    Attributes:
        name: The rejected name, exactly as supplied.
        source: The rule the name broke, as pydantic reported it.
    """

    name: str
    source: ValidationError

    def __init__(self, name: str, *, source: ValidationError) -> None:
        self.name = name
        self.source = source
        super().__init__(f'skill name {name!r} is {len(name)} characters; the limit is {SKILL_NAME_MAX_LENGTH}')
        self.__cause__ = source


class InvalidSkillNameFormatError(Error):
    """A skill name has a character outside lowercase letters, digits and hyphens, or a misplaced hyphen.

    Attributes:
        name: The rejected name, exactly as supplied.
        source: The rule the name broke, as pydantic reported it.
    """

    name: str
    source: ValidationError

    def __init__(self, name: str, *, source: ValidationError) -> None:
        self.name = name
        self.source = source
        super().__init__(
            f'skill name {name!r} must be lowercase letters, digits and single hyphens, '
            'neither starting nor ending with a hyphen'
        )
        self.__cause__ = source


@dataclass(frozen=True, slots=True)
class SkillName:
    """The ``name`` field: at most 64 lowercase ASCII letters, digits and hyphens.

    It neither starts nor ends with a hyphen, and never holds two in a row.

    Parsing preserves the spelling. Whether the name matches the skill's directory is not checked here: that needs
    the directory.

    Attributes:
        value: The validated name, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated skill name.

        Args:
            raw: Candidate skill name, as written in the frontmatter.

        Raises:
            EmptySkillNameError: If the name is empty.
            OverlongSkillNameError: If the name has more characters than the specification allows.
            InvalidSkillNameFormatError: If the name is not lowercase letters, digits and single hyphens.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing the name invariant.

        Raises:
            EmptySkillNameError: If the name is empty.
            OverlongSkillNameError: If the name has more characters than the specification allows.
            InvalidSkillNameFormatError: If the name is not lowercase letters, digits and single hyphens.
        """
        try:
            _SKILL_NAME_RULES.validate_python(self.value)
        except ValidationError as exc:
            # pydantic stops at the first rule broken and reports it by its error type.
            match exc.errors()[0]['type']:
                case 'string_too_short':
                    raise EmptySkillNameError(source=exc) from exc
                case 'string_too_long':
                    raise OverlongSkillNameError(self.value, source=exc) from exc
                case _:
                    raise InvalidSkillNameFormatError(self.value, source=exc) from exc

    def __str__(self) -> str:
        """The name exactly as written in the frontmatter."""
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
            cls._from_pydantic, serialization=core_schema.plain_serializer_function_ser_schema(str)
        )

    @classmethod
    def _from_pydantic(cls, value: object) -> Self:
        """Take a `SkillName` as it is and parse a string into one, raising pydantic's own error for anything else.

        Args:
            value: The input pydantic holds for the field: an instance, a string, or anything else.
        """
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise PydanticCustomError('string_type', 'Input should be a valid string')
        try:
            return cls.parse(value)
        except (EmptySkillNameError, OverlongSkillNameError, InvalidSkillNameFormatError) as exc:
            raise PydanticCustomError(_NAME_ERROR_TYPE, '{reason}', {'reason': str(exc)}) from exc

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """The JSON Schema of a field of this type: the rules `__post_init__` checks.

        Args:
            schema: The core schema pydantic built for the field; unused, because the JSON Schema is fixed.
            handler: Pydantic's JSON Schema generator; unused for the same reason.
        """
        return _SKILL_NAME_RULES.json_schema()


SKILL_DESCRIPTION_MAX_LENGTH: Final[int] = 1024
"""The most characters a skill description may have."""

# A pattern matches anywhere in the string, as in JSON Schema, so `\S` states "holds a non-whitespace character".
_SKILL_DESCRIPTION_RULES: Final[TypeAdapter[str]] = TypeAdapter(
    Annotated[str, StringConstraints(min_length=1, max_length=SKILL_DESCRIPTION_MAX_LENGTH, pattern=r'\S')]
)
"""A skill description's rules, declared once: ``SkillDescription`` checks them and renders its JSON Schema from
them."""


class EmptySkillDescriptionError(Error):
    """A skill description is empty, or holds nothing but whitespace.

    Attributes:
        source: The rule the description broke, as pydantic reported it.
    """

    source: ValidationError

    def __init__(self, *, source: ValidationError) -> None:
        self.source = source
        super().__init__('skill description cannot be empty')
        self.__cause__ = source


class OverlongSkillDescriptionError(Error):
    """A skill description has more characters than the specification allows.

    Attributes:
        description: The rejected description, exactly as supplied.
        source: The rule the description broke, as pydantic reported it.
    """

    description: str
    source: ValidationError

    def __init__(self, description: str, *, source: ValidationError) -> None:
        self.description = description
        self.source = source
        super().__init__(
            f'skill description is {len(description)} characters; the limit is {SKILL_DESCRIPTION_MAX_LENGTH}'
        )
        self.__cause__ = source


@dataclass(frozen=True, slots=True)
class SkillDescription:
    """The ``description`` field: at least one character that is not whitespace, and at most 1024 characters.

    Whether it says what the skill does and when to use it, as the specification asks, is a judgment no check makes.

    Attributes:
        value: The validated description, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated skill description.

        Args:
            raw: Candidate skill description, as written in the frontmatter.

        Raises:
            EmptySkillDescriptionError: If the description is empty or only whitespace.
            OverlongSkillDescriptionError: If the description has more characters than the specification allows.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing the description invariant.

        Raises:
            EmptySkillDescriptionError: If the description is empty or only whitespace.
            OverlongSkillDescriptionError: If the description has more characters than the specification allows.
        """
        try:
            _SKILL_DESCRIPTION_RULES.validate_python(self.value)
        except ValidationError as exc:
            # pydantic stops at the first rule broken and reports it by its error type. Too short and no
            # non-whitespace character are both a blank description.
            match exc.errors()[0]['type']:
                case 'string_too_long':
                    raise OverlongSkillDescriptionError(self.value, source=exc) from exc
                case _:
                    raise EmptySkillDescriptionError(source=exc) from exc

    def __str__(self) -> str:
        """The description exactly as written in the frontmatter."""
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
            cls._from_pydantic, serialization=core_schema.plain_serializer_function_ser_schema(str)
        )

    @classmethod
    def _from_pydantic(cls, value: object) -> Self:
        """Take a `SkillDescription` as it is and parse a string into one.

        Anything else raises pydantic's own error.

        Args:
            value: The input pydantic holds for the field: an instance, a string, or anything else.
        """
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise PydanticCustomError('string_type', 'Input should be a valid string')
        try:
            return cls.parse(value)
        except (EmptySkillDescriptionError, OverlongSkillDescriptionError) as exc:
            raise PydanticCustomError(_DESCRIPTION_ERROR_TYPE, '{reason}', {'reason': str(exc)}) from exc

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """The JSON Schema of a field of this type: the rules `__post_init__` checks.

        Args:
            schema: The core schema pydantic built for the field; unused, because the JSON Schema is fixed.
            handler: Pydantic's JSON Schema generator; unused for the same reason.
        """
        return _SKILL_DESCRIPTION_RULES.json_schema()


@dataclass(frozen=True, slots=True)
class SkillLicense:
    """The ``license`` field: a license's name, or the name of a license file bundled with the skill.

    The specification puts no rule on the text, only a recommendation to keep it short, so every string is valid.
    Whether a named license file exists is not checked here: that needs the skill's directory.

    Attributes:
        value: The license, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return the license; every string is one.

        Args:
            raw: License text, as written in the frontmatter.
        """
        return cls(raw)

    def __str__(self) -> str:
        """The license exactly as written in the frontmatter."""
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
            cls._from_pydantic, serialization=core_schema.plain_serializer_function_ser_schema(str)
        )

    @classmethod
    def _from_pydantic(cls, value: object) -> Self:
        """Take a `SkillLicense` as it is and wrap a string in one.

        Anything else raises pydantic's own error.

        Args:
            value: The input pydantic holds for the field: an instance, a string, or anything else.
        """
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise PydanticCustomError('string_type', 'Input should be a valid string')
        return cls.parse(value)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """The JSON Schema of a field of this type: any string.

        Args:
            schema: The core schema pydantic built for the field; unused, because the JSON Schema is fixed.
            handler: Pydantic's JSON Schema generator; unused for the same reason.
        """
        return {'type': 'string'}


SKILL_COMPATIBILITY_MAX_LENGTH: Final[int] = 500
"""The most characters a skill compatibility note may have."""

# A pattern matches anywhere in the string, as in JSON Schema, so `\S` states "holds a non-whitespace character".
_SKILL_COMPATIBILITY_RULES: Final[TypeAdapter[str]] = TypeAdapter(
    Annotated[str, StringConstraints(min_length=1, max_length=SKILL_COMPATIBILITY_MAX_LENGTH, pattern=r'\S')]
)
"""A skill compatibility note's rules, declared once: ``SkillCompatibility`` checks them and renders its JSON
Schema from them."""


class EmptySkillCompatibilityError(Error):
    """A skill compatibility note is empty, or holds nothing but whitespace.

    Attributes:
        source: The rule the note broke, as pydantic reported it.
    """

    source: ValidationError

    def __init__(self, *, source: ValidationError) -> None:
        self.source = source
        super().__init__('skill compatibility cannot be empty; leave the field out instead')
        self.__cause__ = source


class OverlongSkillCompatibilityError(Error):
    """A skill compatibility note has more characters than the specification allows.

    Attributes:
        compatibility: The rejected note, exactly as supplied.
        source: The rule the note broke, as pydantic reported it.
    """

    compatibility: str
    source: ValidationError

    def __init__(self, compatibility: str, *, source: ValidationError) -> None:
        self.compatibility = compatibility
        self.source = source
        super().__init__(
            f'skill compatibility is {len(compatibility)} characters; the limit is {SKILL_COMPATIBILITY_MAX_LENGTH}'
        )
        self.__cause__ = source


@dataclass(frozen=True, slots=True)
class SkillCompatibility:
    """The ``compatibility`` field, the environment the skill needs.

    It holds at least one character that is not whitespace, and at most 500 characters.

    Attributes:
        value: The validated note, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return a validated compatibility note.

        Args:
            raw: Candidate compatibility note, as written in the frontmatter.

        Raises:
            EmptySkillCompatibilityError: If the note is empty or only whitespace.
            OverlongSkillCompatibilityError: If the note has more characters than the specification allows.
        """
        return cls(raw)

    def __post_init__(self) -> None:
        """Keep direct construction from bypassing the compatibility invariant.

        Raises:
            EmptySkillCompatibilityError: If the note is empty or only whitespace.
            OverlongSkillCompatibilityError: If the note has more characters than the specification allows.
        """
        try:
            _SKILL_COMPATIBILITY_RULES.validate_python(self.value)
        except ValidationError as exc:
            # pydantic stops at the first rule broken and reports it by its error type. Too short and no
            # non-whitespace character are both a blank note.
            match exc.errors()[0]['type']:
                case 'string_too_long':
                    raise OverlongSkillCompatibilityError(self.value, source=exc) from exc
                case _:
                    raise EmptySkillCompatibilityError(source=exc) from exc

    def __str__(self) -> str:
        """The compatibility note exactly as written in the frontmatter."""
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
            cls._from_pydantic, serialization=core_schema.plain_serializer_function_ser_schema(str)
        )

    @classmethod
    def _from_pydantic(cls, value: object) -> Self:
        """Take a `SkillCompatibility` as it is and parse a string into one.

        Anything else raises pydantic's own error.

        Args:
            value: The input pydantic holds for the field: an instance, a string, or anything else.
        """
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise PydanticCustomError('string_type', 'Input should be a valid string')
        try:
            return cls.parse(value)
        except (EmptySkillCompatibilityError, OverlongSkillCompatibilityError) as exc:
            raise PydanticCustomError(_COMPATIBILITY_ERROR_TYPE, '{reason}', {'reason': str(exc)}) from exc

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """The JSON Schema of a field of this type: the rules `__post_init__` checks.

        Args:
            schema: The core schema pydantic built for the field; unused, because the JSON Schema is fixed.
            handler: Pydantic's JSON Schema generator; unused for the same reason.
        """
        return _SKILL_COMPATIBILITY_RULES.json_schema()


@dataclass(frozen=True, slots=True)
class SkillAllowedTools:
    """The ``allowed-tools`` field: the tools the skill may run without asking.

    The specification calls it a space-separated string and marks it experimental, and puts no rule on the text,
    so every string is valid. It is kept whole rather than split into tools: a rule such as ``Bash(git add *)``
    holds spaces of its own, and how an agent splits the string is the agent's.

    Attributes:
        value: The tools, exactly as supplied.
    """

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Return the allowed tools; every string is a list of them.

        Args:
            raw: The `allowed-tools` text, as written in the frontmatter. Kept whole.
        """
        return cls(raw)

    def __str__(self) -> str:
        """The tools exactly as written in the frontmatter, unsplit."""
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
            cls._from_pydantic, serialization=core_schema.plain_serializer_function_ser_schema(str)
        )

    @classmethod
    def _from_pydantic(cls, value: object) -> Self:
        """Take a `SkillAllowedTools` as it is and wrap a string in one.

        Anything else raises pydantic's own error.

        Args:
            value: The input pydantic holds for the field: an instance, a string, or anything else.
        """
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise PydanticCustomError('string_type', 'Input should be a valid string')
        return cls.parse(value)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """The JSON Schema of a field of this type: any string.

        Args:
            schema: The core schema pydantic built for the field; unused, because the JSON Schema is fixed.
            handler: Pydantic's JSON Schema generator; unused for the same reason.
        """
        return {'type': 'string'}


class SkillFrontmatter(BaseModel):
    """The frontmatter a skill's `SKILL.md` opens with: what an agent loads for every skill at startup."""

    model_config = ConfigDict(
        extra='forbid',
        frozen=True,
        strict=True,
        use_attribute_docstrings=True,
        title='Agent Skill frontmatter',
        json_schema_extra={
            'examples': [
                {
                    'name': 'skill-name',
                    'description': 'A description of what this skill does and when to use it.',
                },
                {
                    'name': 'pdf-processing',
                    'description': 'Extract PDF text, fill forms, merge files. Use when handling PDFs.',
                    'license': 'Apache-2.0',
                    'metadata': {'author': 'example-org', 'version': '1.0'},
                },
            ],
        },
    )

    name: SkillName = Field(examples=['pdf-processing', 'data-analysis', 'code-review'])
    """The skill's name: lowercase letters, digits and hyphens, neither starting nor ending with a hyphen and
    never two in a row. It must match the name of the directory the skill sits in."""
    description: SkillDescription = Field(
        examples=[
            'Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working'
            ' with PDF documents or when the user mentions PDFs, forms, or document extraction.'
        ],
    )
    """What the skill does and when to use it, with the keywords that let an agent match it to a task."""
    license: SkillLicense | None = Field(
        default=None, examples=['Apache-2.0', 'Proprietary. LICENSE.txt has complete terms']
    )
    """The license the skill is under: a license's name, or the name of a license file bundled with the skill."""
    compatibility: SkillCompatibility | None = Field(
        default=None,
        examples=[
            'Designed for Claude Code (or similar products)',
            'Requires git, docker, jq, and access to the internet',
            'Requires Python 3.14+ and uv',
        ],
    )
    """The environment the skill needs: the product it is meant for, the system packages it runs, or network
    access. Most skills need none, and leave it out."""
    metadata: dict[str, str] | None = Field(default=None, examples=[{'author': 'example-org', 'version': '1.0'}])
    """Properties the specification does not define, for clients to read: string keys to string values, so a
    number is quoted. Keys are best made unique enough not to collide with another client's."""
    # `allowed-tools` is no Python name, so the field is declared under another and read by its alias.
    allowed_tools: SkillAllowedTools | None = Field(
        default=None,
        alias='allowed-tools',
        examples=['Read Grep', 'Bash(git add *) Bash(git commit *) Bash(git status *)', 'Bash(gh *)'],
    )
    """The tools the skill may run without asking, separated by spaces. Experimental: support for it varies
    between agents."""
