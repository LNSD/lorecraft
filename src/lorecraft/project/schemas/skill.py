"""The Agent Skills specification as a frontmatter schema: what it says is wrong with a skill's frontmatter.

``SkillFrontmatter`` declares the specification's fields once, and pydantic holds a decoded frontmatter to it.
``SkillFrontmatterSchema`` is the seam where pydantic's errors are translated into ``FrontmatterProblem`` values,
in the shape ``FrontmatterSchema`` reports a document's in, so the skill check and the frontmatter check read one
shape. The messages are Lorecraft's own: the specification is fixed, so a reader is told what it requires in
words that do not change with pydantic's version.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Final

from pydantic import ValidationError
from pydantic_core import ErrorDetails

from lorecraft.core.mapping import Frozen, FrozenMapping

from .frontmatter_problem import (
    BlockProblem,
    FieldGuidance,
    FrontmatterProblem,
    InvalidValueProblem,
    JsonType,
    MissingFieldProblem,
    OtherBlockConstraint,
    OtherValueConstraint,
    PatternMismatch,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from .schema_guidance import json_type_of, known_fields, schema_guidance
from .skill_frontmatter import SKILL_NAME_PATTERN, SkillFrontmatter, find_value_object_message, is_name_format_error


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
                problems.append(_frontmatter_problem(detail, len(data)))
            return tuple(problems)
        return ()


SKILL_FRONTMATTER_SCHEMA: Final[SkillFrontmatterSchema] = SkillFrontmatterSchema()
"""The Agent Skills specification every skill's frontmatter is held to."""


_SPECIFIED_FIELDS: Final[tuple[str, ...]] = known_fields(SkillFrontmatter.model_json_schema())
"""The fields the specification defines, in the order it declares them."""


def _field_guidance() -> Mapping[str, FieldGuidance]:
    """What the specification states about each of its fields, read from the JSON Schema the model renders.

    The model's descriptions are its attribute docstrings, wrapped at the source's line width, so each is unwrapped
    into the one line a reader sees.
    """
    specification = SkillFrontmatter.model_json_schema()
    guidance: dict[str, FieldGuidance] = {}
    for field, schema in specification['properties'].items():
        stated = schema_guidance(schema)
        if stated.description is not None:
            stated = replace(stated, description=' '.join(stated.description.split()))
        guidance[field] = stated
    return MappingProxyType(guidance)


_FIELD_GUIDANCE: Final[Mapping[str, FieldGuidance]] = _field_guidance()
"""What the specification states about each field, by the name the frontmatter writes it under."""


def _frontmatter_problem(detail: ErrorDetails, field_count: int) -> FrontmatterProblem:
    """One pydantic error, as the problem it reports on the top-level field it concerns.

    Args:
        detail: One entry of a pydantic `ValidationError`; its `loc` and `type` pick the problem reported.
        field_count: The number of top-level fields the frontmatter holds, which a problem of the whole block states.
    """
    location = detail['loc']
    if not location:
        # pydantic locates every problem of a mapping at a key; one that names none concerns the block.
        message = 'the frontmatter does not satisfy the Agent Skills specification'
        return BlockProblem(message, OtherBlockConstraint(), field_count)
    field = str(location[0])
    # A field the specification does not define has none to state.
    guidance = _FIELD_GUIDANCE.get(field, FieldGuidance())
    if len(location) > 1:
        return InvalidValueProblem(field, _nested_message(field, detail), OtherValueConstraint(), guidance=guidance)
    value_object_reason = find_value_object_message(detail)
    if value_object_reason is not None:
        # A name's characters are the one value-object rejection a pattern states, as a document's are.
        constraint = PatternMismatch(SKILL_NAME_PATTERN) if is_name_format_error(detail) else OtherValueConstraint()
        return InvalidValueProblem(field, value_object_reason, constraint, guidance=guidance)
    match detail['type']:
        case 'missing':
            return MissingFieldProblem(field, f'`{field}` is required', guidance=guidance)
        case 'extra_forbidden':
            message = f'`{field}` is not a field of the Agent Skills specification'
            return UnknownFieldProblem(field, message, _SPECIFIED_FIELDS)
        case 'string_type':
            found = json_type_of(detail['input'])
            return WrongTypeProblem(field, f'`{field}` must be a string', (JsonType.STRING,), found, guidance=guidance)
        case 'dict_type':
            message = f'`{field}` must be a mapping of strings to strings'
            found = json_type_of(detail['input'])
            return WrongTypeProblem(field, message, (JsonType.OBJECT,), found, guidance=guidance)
        case _:
            return InvalidValueProblem(field, _unspecified_message(field), OtherValueConstraint(), guidance=guidance)


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
