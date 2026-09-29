"""Validate one document's frontmatter against the header schemas that govern it.

The check is pure: it takes the already decoded, already validated header schemas that govern a document, the
document's frontmatter node, and the filename and corpus the frontmatter is checked against, and returns violations.
It reads those and nothing else, so it is handed that node rather than the whole parse tree, and not the document's
path: the run that called it attaches that. Reading and parsing the document, choosing the schemas and deciding what
a decode failure means all happen above it, in ``checks.run`` and the database.
"""

from dataclasses import dataclass
from typing import Final

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.schemas import HeaderAspect
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
"""Where a violation with no more precise position is reported: a missing block, a missing key."""


@dataclass(frozen=True, slots=True)
class HeaderCheckResult:
    """What the header check found in one document.

    Attributes:
        violations: In the order the check finds them; empty when the document conforms.
    """

    violations: tuple[Violation, ...]


def validate_header(
    schemas: tuple[HeaderAspect, ...], *, frontmatter: FrontmatterNode, filename: AspectFilename, corpus: CorpusName
) -> HeaderCheckResult:
    """Check one document's frontmatter against the header schemas that govern it. Pure: raises nothing.

    Args:
        schemas: Applied in order; each violation names the schema's path. Empty means the document is
            ungoverned, which yields no violations.
        filename: The document's filename, which the frontmatter ``name`` must equal (rule
            ``frontmatter.name-matches-filename``).
        corpus: The document's corpus, which namespaces the rule of every schema violation.
    """
    if not schemas:
        return HeaderCheckResult(violations=())

    if isinstance(frontmatter, MissingFrontmatter):
        return _one_violation('frontmatter.missing', 'no `---` delimited frontmatter block')
    if isinstance(frontmatter, InvalidYamlFrontmatter):
        return _one_violation('frontmatter.unparseable', f'frontmatter is not valid YAML: {frontmatter.detail}')
    if isinstance(frontmatter, NonMappingFrontmatter):
        return _one_violation('frontmatter.unparseable', 'frontmatter is not a YAML mapping')

    violations: list[Violation] = []
    expected_name = str(filename)
    name = frontmatter.data.get('name')
    if name != expected_name:
        violations.append(
            Violation(
                line=_key_line(frontmatter, 'name'),
                rule='frontmatter.name-matches-filename',
                message=f'`name` is {name!r}; expected {expected_name!r}',
            )
        )

    rule_namespace = str(corpus)
    for aspect in schemas:
        validator = Draft202012Validator(aspect.schema)
        errors = sorted(
            validator.iter_errors(frontmatter.data),
            key=lambda error: (tuple(str(part) for part in error.path), error.message),
        )
        for error in errors:
            for field in _violated_fields(error):
                rule = f'{rule_namespace}.{field}' if field else f'{rule_namespace}.frontmatter'
                violations.append(
                    Violation(
                        line=_key_line(frontmatter, field) if field else _FIRST_LINE,
                        rule=rule,
                        message=f'{error.message} (per {aspect.path})',
                        spec=aspect.path,
                    )
                )

    return HeaderCheckResult(violations=tuple(violations))


def _one_violation(rule: str, message: str) -> HeaderCheckResult:
    """The result of a document whose frontmatter is unusable: one violation on its first line."""
    return HeaderCheckResult(violations=(Violation(line=_FIRST_LINE, rule=rule, message=message),))


def _key_line(frontmatter: Frontmatter, key: str) -> LineNumber:
    """The line a top-level key is written on, or line 1 when the frontmatter does not have it."""
    line = frontmatter.key_line(key)
    if line is None:
        return _FIRST_LINE
    return line


def _violated_fields(error: ValidationError) -> list[str]:
    """Return the top-level fields implicated by one schema error."""
    if error.path:
        return [str(error.path[0])]

    if error.validator == 'required' and isinstance(error.instance, dict):
        return [str(field) for field in error.validator_value if field not in error.instance]

    return ['']
