"""Validate one skill's frontmatter against the Agent Skills specification.

The specification's fields and their limits are declared once, in ``SkillFrontmatter``; this check holds a
skill's frontmatter to that declaration and turns each rejection into a violation on the line of the field it
concerns. The check is pure: it takes the skill's frontmatter node and the name of the directory the skill sits
in, and returns violations. Reading the ``SKILL.md`` and deciding what a decode failure means happen above it, in
``checks.run`` and the database.
"""

from dataclasses import dataclass
from typing import Final, assert_never

from pydantic import ValidationError

from lorecraft.project.schemas import SkillFrontmatter
from lorecraft.project.syntax import (
    Frontmatter,
    FrontmatterNode,
    InvalidYamlFrontmatter,
    LineNumber,
    MissingFrontmatter,
    NonMappingFrontmatter,
)

from .reporting import Violation

_FIRST_LINE: Final[LineNumber] = LineNumber(1)
"""Where a violation with no more precise position is reported: a missing block, a missing field."""

_UNKNOWN_FIELD_ERROR: Final[str] = 'extra_forbidden'
"""The pydantic error type of a field the closed ``SkillFrontmatter`` model does not declare."""

_NON_STRING_KEY_ERROR: Final[str] = 'invalid_key'
"""The pydantic error type of a key YAML decoded to something other than a string, such as ``123`` or ``yes``."""


@dataclass(frozen=True, slots=True)
class SkillCheckResult:
    """What the skill check found in one skill.

    Attributes:
        violations: In the order the check finds them; empty when the skill conforms.
    """

    violations: tuple[Violation, ...]


def validate_skill(frontmatter: FrontmatterNode, *, directory_name: str) -> SkillCheckResult:
    """Check one skill's frontmatter against the Agent Skills specification. Pure: raises nothing.

    A field the specification rejects is rule ``skill.<field>``, a field it does not define is
    ``skill.unknown-field``, and a ``name`` that differs from the skill's directory is
    ``skill.name-matches-directory``.

    Args:
        frontmatter: The frontmatter node of the skill's ``SKILL.md``.
        directory_name: The name of the directory the skill sits in, which the frontmatter ``name`` must equal.
    """
    match frontmatter:
        case MissingFrontmatter():
            return _one_violation('skill.frontmatter-missing', 'no `---` delimited frontmatter block', _FIRST_LINE)
        case InvalidYamlFrontmatter(problem=problem, line=line):
            return _one_violation(
                'skill.frontmatter-unparseable', f'frontmatter is not valid YAML: {problem}', line or _FIRST_LINE
            )
        case NonMappingFrontmatter():
            return _one_violation('skill.frontmatter-unparseable', 'frontmatter is not a YAML mapping', _FIRST_LINE)
        case Frontmatter():
            pass  # the mapping is checked below
        case _:
            assert_never(frontmatter)

    violations: list[Violation] = []
    try:
        SkillFrontmatter.model_validate(frontmatter.data)
    except ValidationError as exc:
        violations.extend(_specification_violations(frontmatter, exc))

    # A name of the wrong type, or none, is the specification's violation above; the directory is compared
    # only with a name there is.
    name = frontmatter.data.get('name')
    if isinstance(name, str) and name != directory_name:
        violations.append(
            Violation(
                line=_key_line(frontmatter, 'name'),
                rule='skill.name-matches-directory',
                message=f'`name` is {name!r}; expected {directory_name!r}, the name of the skill directory',
            )
        )

    return SkillCheckResult(violations=tuple(violations))


def _specification_violations(frontmatter: Frontmatter, error: ValidationError) -> list[Violation]:
    """One violation per problem pydantic found, each on the line of the top-level field it concerns."""
    violations: list[Violation] = []
    for detail in error.errors(include_url=False):
        location = [str(part) for part in detail['loc']]
        if not location:
            # pydantic locates every problem of a mapping at a field; one that names none concerns the block.
            violations.append(Violation(line=_FIRST_LINE, rule='skill.frontmatter', message=detail['msg']))
            continue
        if detail['type'] == _NON_STRING_KEY_ERROR:
            # No field is named by such a key, and pydantic reports the decoded value rather than what was
            # written (``yes`` comes back as ``1``), so the message names no key. The frontmatter node records
            # a line for string keys only, so there is none to report it on.
            message = 'a key that is not a string is not a field of the Agent Skills specification'
            violations.append(Violation(line=_FIRST_LINE, rule='skill.unknown-field', message=message))
            continue
        field = location[0]
        if detail['type'] == _UNKNOWN_FIELD_ERROR:
            rule = 'skill.unknown-field'
            message = f'`{field}` is not a field of the Agent Skills specification'
        else:
            rule = f'skill.{field}'
            message = f'`{".".join(location)}`: {detail["msg"]}'
        violations.append(Violation(line=_key_line(frontmatter, field), rule=rule, message=message))
    return violations


def _one_violation(rule: str, message: str, line: LineNumber) -> SkillCheckResult:
    """The result of a skill whose frontmatter is unusable: one violation, on the line it is found at."""
    return SkillCheckResult(violations=(Violation(line=line, rule=rule, message=message),))


def _key_line(frontmatter: Frontmatter, key: str) -> LineNumber:
    """The line a top-level key is written on, or line 1 when the frontmatter does not have it."""
    line = frontmatter.key_line(key)
    if line is None:
        return _FIRST_LINE
    return line
