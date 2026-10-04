"""Where a frontmatter problem is reported: the rule it breaks and the line it is found on.

The frontmatter check and the skill check read the same ``FrontmatterProblem`` values from their schemas, so
both place a problem the same way; only the namespace of the rule differs, the corpus or ``skill``.
"""

from typing import Final, assert_never

from lorecraft.project.schemas import (
    BlockProblem,
    FrontmatterProblem,
    InvalidValueProblem,
    MissingFieldProblem,
    NonStringKeyProblem,
    NotAStringMappingProblem,
    NotAStringProblem,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from lorecraft.project.syntax import Frontmatter, LineNumber

_FIRST_LINE: Final[LineNumber] = LineNumber.parse(1)
"""Where a problem with no more precise position is reported: one on no field, or on a field not written."""


def problem_rule(rule_namespace: str, problem: FrontmatterProblem) -> str:
    """The rule a schema problem breaks.

    `<namespace>.unknown-field` for a key the schema does not define, `<namespace>.frontmatter` for a rule
    over the whole block, and `<namespace>.<field>` for a problem on a field.

    Args:
        rule_namespace: Prefix of the rule: the document's corpus, or `skill`.
        problem: The schema problem to name a rule for.
    """
    match problem:
        case UnknownFieldProblem() | NonStringKeyProblem():
            return f'{rule_namespace}.unknown-field'
        case BlockProblem():
            return f'{rule_namespace}.frontmatter'
        case (
            MissingFieldProblem()
            | NotAStringProblem()
            | NotAStringMappingProblem()
            | WrongTypeProblem()
            | InvalidValueProblem()
        ):
            return f'{rule_namespace}.{problem.field}'
        case _:
            assert_never(problem)


def problem_line(frontmatter: Frontmatter, problem: FrontmatterProblem) -> LineNumber:
    """The line a schema problem is reported on: its field's, or line 1 when it concerns no field.

    Args:
        frontmatter: The frontmatter the problem was found in; searched for the line its field is written on.
        problem: What the schema rejected; a problem naming a field is placed on that field's line.
    """
    match problem:
        case NonStringKeyProblem() | BlockProblem():
            return _FIRST_LINE
        case (
            MissingFieldProblem()
            | UnknownFieldProblem()
            | NotAStringProblem()
            | NotAStringMappingProblem()
            | WrongTypeProblem()
            | InvalidValueProblem()
        ):
            return field_line(frontmatter, problem.field)
        case _:
            assert_never(problem)


def field_line(frontmatter: Frontmatter, field: str) -> LineNumber:
    """The line a top-level field is written on, or line 1 when the frontmatter lacks it.

    Args:
        frontmatter: The decoded frontmatter, whose top-level keys carry the line each is written on.
        field: Name of the top-level key to find.
    """
    line = frontmatter.find_key_line(field)
    if line is None:
        return _FIRST_LINE
    return line
