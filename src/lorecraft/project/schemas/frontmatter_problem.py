"""What a frontmatter schema says is wrong with one frontmatter, in the one shape every schema reports in.

Two kinds of schema govern a frontmatter: the JSON Schema a structure specification states for a corpus, which
``FrontmatterSchema`` applies with ``jsonschema``, and the Agent Skills specification, which
``SkillFrontmatterSchema`` applies with pydantic. Each translates its validator's errors into
``FrontmatterProblem`` values at its own seam, so a check reads the same shape from either and never reads a
validator's error record.

Each cause is its own class. A problem on a top-level field names it; the one cause that concerns no field, a
rule over the whole block, has no ``field`` at all. Besides what is wrong, a problem carries what the schema
states that tells a reader how to put it right, as typed data: the field's description and an example, the
values it allows, the types it expects, the limit it sets. The prose a validator words is kept as ``message``,
for the one cause no typed constraint describes.
"""

from dataclasses import KW_ONLY, dataclass
from enum import Enum


class JsonType(Enum):
    """A type JSON Schema names; the value is the name its `type` keyword spells it with."""

    ARRAY = 'array'
    BOOLEAN = 'boolean'
    INTEGER = 'integer'
    NULL = 'null'
    NUMBER = 'number'
    OBJECT = 'object'
    STRING = 'string'


@dataclass(frozen=True, slots=True)
class FieldGuidance:
    """What a schema states about one field, to tell a reader how to write it.

    Every part is optional: a schema is under no obligation to describe its fields, and the default states nothing.

    Attributes:
        description: What the field is for, as the schema wrote it, or `None` when it states none.
        example: The first example the schema gives, or the one value it allows, as text; or `None` when it gives
            none.
        allowed: The values the field is restricted to by `enum` or `const`, each as text; empty when it is not.
    """

    description: str | None = None
    example: str | None = None
    allowed: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OneOfValues:
    """The value is not one of the values an `enum` or a `const` allows.

    Attributes:
        values: The allowed values, each as text.
    """

    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PatternMismatch:
    """The text does not match a `pattern`.

    Attributes:
        pattern: The regular expression, as the schema wrote it.
    """

    pattern: str


@dataclass(frozen=True, slots=True)
class OtherValueConstraint:
    """The value breaks a keyword no typed constraint describes; the problem's `message` is all there is to say."""


type ValueConstraint = OneOfValues | PatternMismatch | OtherValueConstraint
"""The constraint a value broke: what the field's label and its allowed values are drawn from."""


@dataclass(frozen=True, slots=True)
class MinFields:
    """The block holds fewer fields than `minProperties` requires.

    Attributes:
        limit: The least number of fields the schema requires.
    """

    limit: int


@dataclass(frozen=True, slots=True)
class MaxFields:
    """The block holds more fields than `maxProperties` allows.

    Attributes:
        limit: The most fields the schema allows.
    """

    limit: int


@dataclass(frozen=True, slots=True)
class OtherBlockConstraint:
    """The block breaks a keyword no typed constraint describes; the problem's `message` is all there is to say."""


type BlockLimit = MinFields | MaxFields | OtherBlockConstraint
"""The constraint over the whole block that it broke."""


@dataclass(frozen=True, slots=True)
class MissingFieldProblem:
    """A field the schema requires is absent.

    Attributes:
        field: The absent field, as the schema names it.
        message: What a reader is told, naming the field.
        guidance: What the schema states about the field; empty when it has no property for it, as when `required`
            sits in a branch that leaves `properties` to the schema around it.
    """

    field: str
    message: str
    _: KW_ONLY
    guidance: FieldGuidance = FieldGuidance()


@dataclass(frozen=True, slots=True)
class UnknownFieldProblem:
    """A field the schema does not define.

    Attributes:
        field: The field as written in the frontmatter.
        message: What a reader is told, naming the field.
        known_fields: The fields the schema defines, in the order it states them; empty when it states none. A
            `jsonschema` schema that composes others with `allOf` or `$ref` may evaluate fields its own
            `properties` do not name, so the list holds only the properties of the schema the keyword sits in.
    """

    field: str
    message: str
    known_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WrongTypeProblem:
    """The field's value is of a type the schema does not accept.

    Each schema states the type it expects in its own terms, a JSON Schema ``type`` keyword or a field of the Agent
    Skills specification, so the message names the type expected.

    Attributes:
        field: The field as written in the frontmatter.
        message: What a reader is told, naming the type expected.
        expected: The types the schema accepts.
        found: The type the value has.
        guidance: What the schema states about the field.
    """

    field: str
    message: str
    expected: tuple[JsonType, ...]
    found: JsonType
    _: KW_ONLY
    guidance: FieldGuidance = FieldGuidance()


@dataclass(frozen=True, slots=True)
class InvalidValueProblem:
    """The field's value breaks another rule, such as a length limit or a pattern.

    Also something inside the value that is missing, unknown or of the wrong type: anything wrong below a
    top-level field is that field's value at fault.

    Attributes:
        field: The field as written in the frontmatter.
        message: What a reader is told, naming the field and, below it, the key at fault.
        constraint: The constraint the value broke.
        reason: Why the failing subschema is there, in the words its author gave it in `$comment`; or `None` when
            it states none.
        guidance: What the schema states about the field.
    """

    field: str
    message: str
    constraint: ValueConstraint
    _: KW_ONLY
    reason: str | None = None
    guidance: FieldGuidance = FieldGuidance()


@dataclass(frozen=True, slots=True)
class BlockProblem:
    """A rule over the whole block, such as a least number of fields, which concerns no field.

    Attributes:
        message: What a reader is told.
        constraint: The constraint the block broke.
        field_count: The number of top-level fields the block holds.
        description: What the schema says it describes, as it wrote it, or `None` when it states none.
    """

    message: str
    constraint: BlockLimit
    field_count: int
    _: KW_ONLY
    description: str | None = None


type FrontmatterProblem = (
    MissingFieldProblem | UnknownFieldProblem | WrongTypeProblem | InvalidValueProblem | BlockProblem
)
"""One thing a frontmatter schema rejects."""
