"""Validate one skill's frontmatter against the Agent Skills specification.

The specification is a frontmatter schema, `SkillFrontmatterSchema`, and says what is wrong as
`FrontmatterProblem` values; the check turns each into a violation on the line of the field it concerns and
reads no validator's error record. It is the sibling of the frontmatter check, and keeps its skeleton: the same
guards, then the name, then the problems, then the keys written twice.

The check is pure: it takes the specification, the skill's frontmatter node, the name of the real directory the
skill's files live in and the name of the entry an agent reads it by, and returns violations. Reading the
`SKILL.md`, following the entry's link and deciding what a decode failure means happen above it, in `checks.run`,
the database and the model.
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
from .reporting import Note, NoteKind, Violation

_FIRST_LINE: Final[LineNumber] = LineNumber(1)
"""Where a frontmatter that cannot be checked is reported: a missing block, or one that is not a mapping."""

_RULE_NAMESPACE: Final[str] = 'skill'
"""The namespace of every rule the skill check reports, as the corpus is for the frontmatter check."""

_NAME_RULE: Final[str] = 'skill.name-matches-directory'
"""The rule a `name` breaks when it differs from the name of the real directory the skill's files live in."""


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
    entry_name: str,
) -> SkillCheckResult:
    """Check one skill's frontmatter against the Agent Skills specification. Pure: raises nothing.

    A `name` that differs from the name of the skill directory is `skill.name-matches-directory`. A field the
    specification rejects is `skill.<field>`, a field it does not define is `skill.unknown-field`, and a problem
    that concerns no field is `skill.frontmatter`. A top-level key written again is `skill.duplicate-key`, on each
    later occurrence.

    Args:
        schema: Always `SKILL_FRONTMATTER_SCHEMA`, the one instance.
        frontmatter: The frontmatter node of the skill's `SKILL.md`.
        directory_name: The name of the real directory the skill's files live in, which the frontmatter `name`
            must equal: the entry itself for a regular directory, or the directory a linked entry leads to. A link
            is transparent, as it is to an agent reading the skill. When the `SKILL.md` is itself a link to a file
            elsewhere, this is still the skill directory, never the parent of the file the link leads to.
        entry_name: The name of the entry under the agent's skills directory that the skill is read by. It plays
            no part in the verdict: when it differs from `directory_name`, it only words a note on the finding.
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
            _name_violation(
                name, line=field_line(frontmatter, 'name'), directory_name=directory_name, entry_name=entry_name
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


def _name_violation(name: str, *, line: LineNumber, directory_name: str, entry_name: str) -> Violation:
    """The violation of a `name` that differs from the name of the skill directory.

    When the skill is read through a link named otherwise than the directory, a note names the link, so a reader
    who knows the skill by the link's name sees where the expected name comes from.

    Args:
        name: The frontmatter `name`, as written.
        line: The line `name` is written on.
        directory_name: The name of the real directory the skill's files live in, which `name` must equal.
        entry_name: The name of the entry the agent reads the skill by; it only words the note.
    """
    notes: tuple[Note, ...] = ()
    if entry_name != directory_name:
        notes = (
            Note(
                NoteKind.NOTE, f'the skill is read through the link {entry_name!r}, which leads to {directory_name!r}'
            ),
        )
    return Violation(
        line=line,
        rule=_NAME_RULE,
        message=f'`name` is {name!r}; expected {directory_name!r}, the name of the skill directory',
        notes=notes,
    )


def _one_violation(rule: str, message: str, line: LineNumber) -> SkillCheckResult:
    """The result of a skill whose frontmatter is unusable: one violation, on the line it is found at.

    Args:
        rule: Identifier the violation is reported under.
        message: Explanation printed with the violation.
        line: Line the violation is reported on.
    """
    return SkillCheckResult(violations=(Violation(line=line, rule=rule, message=message),))
