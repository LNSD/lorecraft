"""Validate one skill's frontmatter against the Agent Skills specification.

The specification is a frontmatter schema, ``SkillFrontmatterSchema``, and says what is wrong as
``FrontmatterProblem`` values; the check turns each into a violation on the line of the field it concerns and
reads no validator's error record. It is the sibling of the frontmatter check, and keeps its skeleton: the same
guards, then the name, then the problems, then the keys written twice.

The check is pure: it takes the specification, the skill's frontmatter node and the name of the directory the
skill sits in, and returns violations. Reading the ``SKILL.md`` and deciding what a decode failure means happen
above it, in ``checks.run`` and the database.
"""

from dataclasses import dataclass
from typing import Final, assert_never

from lorecraft.project.schemas import SkillFrontmatterSchema
from lorecraft.project.syntax import (
    Frontmatter,
    FrontmatterNode,
    InvalidYamlFrontmatter,
    LineNumber,
    MissingFrontmatter,
    NonMappingFrontmatter,
)

from .frontmatter_duplicate import duplicate_key_violations
from .frontmatter_problem import field_line, problem_line, problem_rule
from .reporting import Violation

_FIRST_LINE: Final[LineNumber] = LineNumber(1)
"""Where a frontmatter that cannot be checked is reported: a missing block, or one that is not a mapping."""

_RULE_NAMESPACE: Final[str] = 'skill'
"""The namespace of every rule the skill check reports, as the corpus is for the frontmatter check."""


@dataclass(frozen=True, slots=True)
class SkillCheckResult:
    """What the skill check found in one skill.

    Attributes:
        violations: In the order the check finds them; empty when the skill conforms.
    """

    violations: tuple[Violation, ...]


def validate_skill(
    schema: SkillFrontmatterSchema,
    *,
    frontmatter: FrontmatterNode,
    directory_name: str,
) -> SkillCheckResult:
    """Check one skill's frontmatter against the Agent Skills specification. Pure: raises nothing.

    A ``name`` that differs from the skill's directory is ``skill.name-matches-directory``. A field the
    specification rejects is ``skill.<field>``, a field it does not define is ``skill.unknown-field``, and a
    problem that concerns no field is ``skill.frontmatter``. A top-level key written again is ``skill.duplicate-key``,
    on each later occurrence.

    Args:
        schema: Always ``SKILL_FRONTMATTER_SCHEMA``, the one instance.
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

    # Compared only when it is a string, unlike in the frontmatter check: the specification requires a string
    # `name`, so one missing or of another type is the specification's problem below, not this rule's.
    name = frontmatter.data.get('name')
    if isinstance(name, str) and name != directory_name:
        violations.append(
            Violation(
                line=field_line(frontmatter, 'name'),
                rule='skill.name-matches-directory',
                message=f'`name` is {name!r}; expected {directory_name!r}, the name of the skill directory',
            )
        )

    for problem in schema.validate(frontmatter.data):
        violations.append(
            Violation(
                line=problem_line(frontmatter, problem),
                rule=problem_rule(_RULE_NAMESPACE, problem),
                message=problem.message,
            )
        )

    # Its own rule, after every other: the decoder kept one value of a repeated key, and the rules above judged it.
    violations.extend(duplicate_key_violations(frontmatter, rule='skill.duplicate-key'))

    return SkillCheckResult(violations=tuple(violations))


def _one_violation(rule: str, message: str, line: LineNumber) -> SkillCheckResult:
    """The result of a skill whose frontmatter is unusable: one violation, on the line it is found at."""
    return SkillCheckResult(violations=(Violation(line=line, rule=rule, message=message),))
