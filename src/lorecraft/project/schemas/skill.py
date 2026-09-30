"""The Agent Skills specification as a frontmatter schema: what it says is wrong with a skill's frontmatter.

``SkillFrontmatter`` declares the specification's fields once, and pydantic holds a decoded frontmatter to it.
``SkillFrontmatterSchema`` is the seam where pydantic's errors are translated into ``FrontmatterProblem`` values,
in the shape ``FrontmatterSchema`` reports a document's in, so the skill check and the frontmatter check read one
shape. The messages are Lorecraft's own: the specification is fixed, so a reader is told what it requires in
words that do not change with pydantic's version.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from pydantic import ValidationError
from pydantic_core import ErrorDetails

from .frontmatter_problem import FrontmatterProblem, FrontmatterProblemKind
from .skill_frontmatter import SkillFrontmatter, value_object_message

_KEY_LOCATION: Final[str] = '[key]'
"""The location pydantic appends when a mapping's key, rather than its value, is at fault."""


# It holds nothing, since the specification is fixed. It is an object rather than a function so that it has the
# entry point `FrontmatterSchema` has, and the two checks that hold a frontmatter to a schema take it the same way.
@dataclass(frozen=True, slots=True)
class SkillFrontmatterSchema:
    """The Agent Skills specification, as the frontmatter schema every skill is held to.

    ``SKILL_FRONTMATTER_SCHEMA`` is the one instance.
    """

    def validate(self, data: Mapping[object, object]) -> tuple[FrontmatterProblem, ...]:
        """Hold one decoded frontmatter to the specification. Pure: raises nothing.

        Returns:
            One problem per field at fault, in the order the specification declares its fields, or ``()`` when
            the frontmatter conforms.
        """
        try:
            SkillFrontmatter.model_validate(data)
        except ValidationError as exc:
            problems: list[FrontmatterProblem] = []
            for detail in exc.errors(include_url=False):
                problems.append(_frontmatter_problem(detail))
            return tuple(problems)
        return ()


SKILL_FRONTMATTER_SCHEMA: Final[SkillFrontmatterSchema] = SkillFrontmatterSchema()
"""The Agent Skills specification every skill's frontmatter is held to."""


def _frontmatter_problem(detail: ErrorDetails) -> FrontmatterProblem:
    """One pydantic error, as the problem it reports on the top-level field it concerns."""
    location = detail['loc']
    if not location:
        # pydantic locates every problem of a mapping at a key; one that names none concerns the block.
        return FrontmatterProblem(
            None,
            FrontmatterProblemKind.INVALID_VALUE,
            'the frontmatter does not satisfy the Agent Skills specification',
        )
    if detail['type'] == 'invalid_key':
        # No field is named by such a key, and pydantic reports the decoded value rather than what was written
        # (`yes` comes back as `1`), so the message names no key.
        message = 'a key that is not a string is not a field of the Agent Skills specification'
        return FrontmatterProblem(None, FrontmatterProblemKind.UNKNOWN_FIELD, message)

    field = str(location[0])
    if len(location) > 1:
        return FrontmatterProblem(field, FrontmatterProblemKind.INVALID_VALUE, _nested_message(field, detail))
    value_object_reason = value_object_message(detail)
    if value_object_reason is not None:
        return FrontmatterProblem(field, FrontmatterProblemKind.INVALID_VALUE, value_object_reason)
    match detail['type']:
        case 'missing':
            return FrontmatterProblem(field, FrontmatterProblemKind.MISSING, f'`{field}` is required')
        case 'extra_forbidden':
            message = f'`{field}` is not a field of the Agent Skills specification'
            return FrontmatterProblem(field, FrontmatterProblemKind.UNKNOWN_FIELD, message)
        case 'string_type':
            return FrontmatterProblem(field, FrontmatterProblemKind.WRONG_TYPE, f'`{field}` must be a string')
        case 'dict_type':
            message = f'`{field}` must be a mapping of strings to strings'
            return FrontmatterProblem(field, FrontmatterProblemKind.WRONG_TYPE, message)
        case _:
            return FrontmatterProblem(field, FrontmatterProblemKind.INVALID_VALUE, _unspecified_message(field))


def _nested_message(field: str, detail: ErrorDetails) -> str:
    """What is wrong inside a field's value: only ``metadata`` has one, a mapping of strings to strings."""
    if _KEY_LOCATION in detail['loc']:
        return f'`{field}` keys must be strings'
    path = '.'.join(str(part) for part in detail['loc'])
    if detail['type'] == 'string_type':
        return f'`{path}` must be a string'
    return _unspecified_message(path)


def _unspecified_message(path: str) -> str:
    """The message of an error no rule above words."""
    # Never pydantic's text, which changes with its version.
    return f'`{path}` does not satisfy the Agent Skills specification'
