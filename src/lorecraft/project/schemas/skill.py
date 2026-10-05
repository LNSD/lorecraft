"""The Agent Skills specification as a frontmatter schema: what it says is wrong with a skill's frontmatter.

``SkillFrontmatter`` declares the specification's fields once, and pydantic holds a decoded frontmatter to it.
``SkillFrontmatterSchema`` is the seam where pydantic's errors are translated into ``FrontmatterProblem`` values,
in the shape ``FrontmatterSchema`` reports a document's in, so the skill check and the frontmatter check read one
shape. The messages are Lorecraft's own: the specification is fixed, so a reader is told what it requires in
words that do not change with pydantic's version.
"""

from dataclasses import dataclass
from typing import Final

from pydantic import ValidationError
from pydantic_core import ErrorDetails

from lorecraft.core.mapping import Frozen, FrozenMapping

from .frontmatter_problem import (
    BlockProblem,
    FrontmatterProblem,
    InvalidValueProblem,
    MissingFieldProblem,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from .skill_frontmatter import SkillFrontmatter, find_value_object_message


# It holds nothing, since the specification is fixed. It is an object rather than a function so that it has the
# entry point `FrontmatterSchema` has, and the two checks that hold a frontmatter to a schema take it the same way.
@dataclass(frozen=True, slots=True)
class SkillFrontmatterSchema:
    """The Agent Skills specification, as the frontmatter schema every skill is held to.

    ``SKILL_FRONTMATTER_SCHEMA`` is the one instance.
    """

    def validate(self, data: FrozenMapping[str, Frozen]) -> tuple[FrontmatterProblem, ...]:
        """Hold one decoded frontmatter to the specification. Pure: raises nothing.

        Args:
            data: The decoded frontmatter mapping, frozen all the way down, every key a string at any depth.

        Returns:
            One problem per field at fault, in the order the specification declares its fields, or `()` when
            the frontmatter conforms.
        """
        # The model is strict, so it takes a mapping only as a `dict`: the frozen frontmatter is handed to it as
        # plain data, copied from the frozen value.
        try:
            SkillFrontmatter.model_validate(data.to_plain())
        except ValidationError as exc:
            problems: list[FrontmatterProblem] = []
            for detail in exc.errors(include_url=False):
                problems.append(_frontmatter_problem(detail))
            return tuple(problems)
        return ()


SKILL_FRONTMATTER_SCHEMA: Final[SkillFrontmatterSchema] = SkillFrontmatterSchema()
"""The Agent Skills specification every skill's frontmatter is held to."""


def _frontmatter_problem(detail: ErrorDetails) -> FrontmatterProblem:
    """One pydantic error, as the problem it reports on the top-level field it concerns.

    Args:
        detail: One entry of a pydantic `ValidationError`; its `loc` and `type` pick the problem reported.
    """
    location = detail['loc']
    if not location:
        # pydantic locates every problem of a mapping at a key; one that names none concerns the block.
        return BlockProblem('the frontmatter does not satisfy the Agent Skills specification')
    field = str(location[0])
    if len(location) > 1:
        return InvalidValueProblem(field, _nested_message(field, detail))
    value_object_reason = find_value_object_message(detail)
    if value_object_reason is not None:
        return InvalidValueProblem(field, value_object_reason)
    match detail['type']:
        case 'missing':
            return MissingFieldProblem(field, f'`{field}` is required')
        case 'extra_forbidden':
            message = f'`{field}` is not a field of the Agent Skills specification'
            return UnknownFieldProblem(field, message)
        case 'string_type':
            return WrongTypeProblem(field, f'`{field}` must be a string')
        case 'dict_type':
            return WrongTypeProblem(field, f'`{field}` must be a mapping of strings to strings')
        case _:
            return InvalidValueProblem(field, _unspecified_message(field))


def _nested_message(field: str, detail: ErrorDetails) -> str:
    """What is wrong inside a field's value: only `metadata` has one, a mapping of strings to strings.

    Args:
        field: Top-level field the error sits inside.
        detail: The pydantic error, whose `loc` runs past the field into its value.
    """
    path = '.'.join(str(part) for part in detail['loc'])
    if detail['type'] == 'string_type':
        return f'`{path}` must be a string'
    return _unspecified_message(path)


def _unspecified_message(path: str) -> str:
    """The message of an error no rule above words.

    Args:
        path: Dotted location of the value at fault, quoted in the message.
    """
    # Never pydantic's text, which changes with its version.
    return f'`{path}` does not satisfy the Agent Skills specification'
