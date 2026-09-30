"""What a frontmatter schema says is wrong with one frontmatter, in the one shape every schema reports in.

Two kinds of schema govern a frontmatter: the JSON Schema a structure specification states for a corpus, which
``FrontmatterSchema`` applies with ``jsonschema``, and the Agent Skills specification, which
``SkillFrontmatterSchema`` applies with pydantic. Each translates its validator's errors into
``FrontmatterProblem`` values at its own seam, so a check reads the same shape from either and never reads a
validator's error record.
"""

from dataclasses import dataclass
from enum import Enum


class FrontmatterProblemKind(Enum):
    """What is wrong with the top-level field a problem concerns; anything wrong inside its value is that value's."""

    MISSING = 'missing'
    """A field the schema requires is absent."""
    UNKNOWN_FIELD = 'unknown-field'
    """A field the schema does not define, or a top-level key that is not a string."""
    WRONG_TYPE = 'wrong-type'
    """The field's value is of a type the schema does not accept, such as a number where a string is required."""
    INVALID_VALUE = 'invalid-value'
    """The field's value breaks another rule, such as a length limit or a pattern.

    Also something inside the value that is missing, unknown or of the wrong type, and a rule over the whole
    block, which concerns no field.
    """


@dataclass(frozen=True, slots=True)
class FrontmatterProblem:
    """One thing a frontmatter schema rejects.

    Attributes:
        field: The top-level field the problem concerns, as written in the frontmatter, or ``None`` when it
            concerns no field: the whole block, or a key that is not a string.
        kind: With ``field`` set to ``None``, ``UNKNOWN_FIELD`` for a key that is not a string and
            ``INVALID_VALUE`` for a rule over the whole block; no other kind comes without a field.
        message: What a reader is told, naming the field and, below it, the key at fault.
    """

    field: str | None
    kind: FrontmatterProblemKind
    message: str
