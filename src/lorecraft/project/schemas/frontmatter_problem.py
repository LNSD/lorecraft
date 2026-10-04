"""What a frontmatter schema says is wrong with one frontmatter, in the one shape every schema reports in.

Two kinds of schema govern a frontmatter: the JSON Schema a structure specification states for a corpus, which
``FrontmatterSchema`` applies with ``jsonschema``, and the Agent Skills specification, which
``SkillFrontmatterSchema`` applies with pydantic. Each translates its validator's errors into
``FrontmatterProblem`` values at its own seam, so a check reads the same shape from either and never reads a
validator's error record.

Each cause is its own class. A problem on a top-level field names it; the one cause that concerns no field, a
rule over the whole block, has no ``field`` at all.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MissingFieldProblem:
    """A field the schema requires is absent.

    Attributes:
        field: The absent field, as the schema names it.
        message: What a reader is told, naming the field.
    """

    field: str
    message: str


@dataclass(frozen=True, slots=True)
class UnknownFieldProblem:
    """A field the schema does not define.

    Attributes:
        field: The field as written in the frontmatter.
        message: What a reader is told, naming the field.
    """

    field: str
    message: str


@dataclass(frozen=True, slots=True)
class WrongTypeProblem:
    """The field's value is of a type the schema does not accept.

    Each schema states the type it expects in its own terms, a JSON Schema ``type`` keyword or a field of the Agent
    Skills specification, so the message names the type expected.

    Attributes:
        field: The field as written in the frontmatter.
        message: What a reader is told, naming the type expected.
    """

    field: str
    message: str


@dataclass(frozen=True, slots=True)
class InvalidValueProblem:
    """The field's value breaks another rule, such as a length limit or a pattern.

    Also something inside the value that is missing, unknown or of the wrong type: anything wrong below a
    top-level field is that field's value at fault.

    Attributes:
        field: The field as written in the frontmatter.
        message: What a reader is told, naming the field and, below it, the key at fault.
    """

    field: str
    message: str


@dataclass(frozen=True, slots=True)
class BlockProblem:
    """A rule over the whole block, such as a least number of fields, which concerns no field.

    Attributes:
        message: What a reader is told.
    """

    message: str


type FrontmatterProblem = (
    MissingFieldProblem | UnknownFieldProblem | WrongTypeProblem | InvalidValueProblem | BlockProblem
)
"""One thing a frontmatter schema rejects."""
