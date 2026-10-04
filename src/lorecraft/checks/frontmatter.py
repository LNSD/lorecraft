"""Validate one document's frontmatter against the frontmatter schemas that govern it.

Each schema is the ``frontmatter`` key of a structure specification, and says what is wrong as
``FrontmatterProblem`` values; the check turns each into a violation on the line of the field it concerns and
reads no validator's error record. It is the sibling of the skill check, and keeps its skeleton: the same guards,
then the name, then the problems, then the keys written twice.

The check is pure: it takes the already decoded, already validated frontmatter schemas that govern a document,
the document's frontmatter node, and the filename and corpus the frontmatter is checked against, and returns
violations. It reads those and nothing else, so it is handed that node rather than the whole parse tree, and not
the document's path: the run that called it attaches that. Reading and parsing the document, choosing the schemas
and deciding what a decode failure means all happen above it, in ``checks.run`` and the database.
"""

from dataclasses import dataclass
from typing import Final, assert_never

from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.schemas import FrontmatterSchema
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

_FIRST_LINE: Final[LineNumber] = LineNumber.parse(1)
"""Where a frontmatter that cannot be checked is reported: a missing block, or one that is not a mapping."""


@dataclass(frozen=True, slots=True)
class FrontmatterCheckResult:
    """What the frontmatter check found in one document.

    Attributes:
        violations: In the order the check finds them; empty when the document conforms.
    """

    violations: tuple[Violation, ...]


def validate_frontmatter(
    schemas: tuple[FrontmatterSchema, ...],
    *,
    frontmatter: FrontmatterNode,
    filename: AspectFilename,
    corpus: CorpusName,
) -> FrontmatterCheckResult:
    """Check one document's frontmatter against the frontmatter schemas that govern it. Pure: raises nothing.

    A `name` that differs from the filename is `frontmatter.name-matches-filename`. A field a schema rejects
    is `<corpus>.<field>`, a field it does not allow is `<corpus>.unknown-field`, and a problem that concerns
    no field is `<corpus>.frontmatter`. A top-level key written again is `frontmatter.duplicate-key`, on each
    later occurrence.

    Args:
        schemas: Applied in order; each violation names the structure specification the schema is written in.
            Empty means the document is ungoverned, which yields no violations.
        frontmatter: The document's frontmatter node; a missing, unparseable or non-mapping block is itself the
            only violation.
        filename: The document's filename, which the frontmatter `name` must equal.
        corpus: The document's corpus, which namespaces the rule of every schema violation.
    """
    # The skill check has no such guard: every skill is held to the Agent Skills specification, while a document
    # no structure specification governs is not checked at all.
    if not schemas:
        return FrontmatterCheckResult(violations=())

    match frontmatter:
        case MissingFrontmatter():
            return _one_violation('frontmatter.missing', 'no `---` delimited frontmatter block', _FIRST_LINE)
        case InvalidYamlFrontmatter(problem=problem, line=line):
            return _one_violation(
                'frontmatter.unparseable', f'frontmatter is not valid YAML: {problem}', line or _FIRST_LINE
            )
        case NonMappingFrontmatter():
            return _one_violation('frontmatter.unparseable', 'frontmatter is not a YAML mapping', _FIRST_LINE)
        case Frontmatter():
            pass  # the mapping is checked below
        case _:
            assert_never(frontmatter)

    violations: list[Violation] = []

    # Compared whatever its type, unlike in the skill check: a corpus schema need not require `name`, so this is
    # the rule that reports one missing. The Agent Skills specification requires it, so the skill check need not.
    expected_name = str(filename)
    name = frontmatter.data.get('name')
    if name != expected_name:
        violations.append(
            Violation(
                line=field_line(frontmatter, 'name'),
                rule='frontmatter.name-matches-filename',
                message=f"`name` is {name!r}; expected {expected_name!r}, the document's filename",
            )
        )

    # Unlike the skill check's, each violation names the specification the schema is written in, since a
    # document may be governed by several; the Agent Skills specification is no file in the repository.
    rule_namespace = str(corpus)
    for schema in schemas:
        for problem in schema.validate(frontmatter.data):
            violations.append(
                Violation(
                    line=problem_line(frontmatter, problem),
                    rule=problem_rule(rule_namespace, problem),
                    message=f'{problem.message} (per {schema.path})',
                    spec=schema.path,
                )
            )

    # Its own rule, after every other: the decoder kept one value of a repeated key, and the rules above judged it.
    violations.extend(duplicate_key_violations(frontmatter, rule='frontmatter.duplicate-key'))

    return FrontmatterCheckResult(violations=tuple(violations))


def _one_violation(rule: str, message: str, line: LineNumber) -> FrontmatterCheckResult:
    """The result of a document whose frontmatter is unusable: one violation, on the line it is found at.

    Args:
        rule: Identifier the violation is reported under.
        message: Explanation printed with the violation.
        line: Line the violation is reported on.
    """
    return FrontmatterCheckResult(violations=(Violation(line=line, rule=rule, message=message),))
