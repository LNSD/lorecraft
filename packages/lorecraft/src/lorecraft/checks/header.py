"""Validate one document's frontmatter against the header schemas that govern it.

The check is pure: it takes the document's parse tree, its ref and the already decoded, already validated
header schemas, and returns findings. Reading and parsing the document, choosing the schemas and deciding what
a decode failure means all happen above it, in ``checks.run`` and the database.
"""

from dataclasses import dataclass
from typing import Final

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from lorecraft_project.document import DocumentRef
from lorecraft_project.schemas import HeaderAspect
from lorecraft_project.syntax import (
    Frontmatter,
    InvalidYamlFrontmatter,
    LineNumber,
    MissingFrontmatter,
    NonMappingFrontmatter,
    ParsedDocument,
)

from .reporting import Finding

_FIRST_LINE: Final[LineNumber] = LineNumber(1)
"""Where a finding with no more precise position is reported: a missing block, a missing key."""


@dataclass(frozen=True, slots=True)
class HeaderCheckResult:
    """Findings produced by checking one document's frontmatter.

    Attributes:
        findings: Immutable findings produced by the check.
    """

    findings: tuple[Finding, ...]


def validate_header(document: ParsedDocument, ref: DocumentRef, schemas: tuple[HeaderAspect, ...]) -> HeaderCheckResult:
    """Check one document's parse tree against the header schemas that govern it.

    The report path of every finding is ``ref.path``, schema rule identifiers are namespaced by
    ``str(ref.corpus)``, and the frontmatter ``name`` must equal ``str(ref.filename)`` (rule
    ``frontmatter.name-matches-filename``). Pure: raises nothing.

    Args:
        schemas: Applied in order; each finding names the schema's path. Empty means the document is
            ungoverned, which yields no findings.
    """
    if not schemas:
        return HeaderCheckResult(findings=())

    frontmatter = document.frontmatter
    if isinstance(frontmatter, MissingFrontmatter):
        return _one_finding(ref, 'frontmatter.missing', 'no `---` delimited frontmatter block')
    if isinstance(frontmatter, InvalidYamlFrontmatter):
        return _one_finding(ref, 'frontmatter.unparseable', f'frontmatter is not valid YAML: {frontmatter.detail}')
    if isinstance(frontmatter, NonMappingFrontmatter):
        return _one_finding(ref, 'frontmatter.unparseable', 'frontmatter is not a YAML mapping')

    findings: list[Finding] = []
    expected_name = str(ref.filename)
    name = frontmatter.data.get('name')
    if name != expected_name:
        findings.append(
            Finding(
                path=ref.path,
                line=_key_line(frontmatter, 'name'),
                rule='frontmatter.name-matches-filename',
                message=f'`name` is {name!r}; expected {expected_name!r}',
            )
        )

    rule_namespace = str(ref.corpus)
    for aspect in schemas:
        validator = Draft202012Validator(aspect.schema)
        errors = sorted(
            validator.iter_errors(frontmatter.data),
            key=lambda error: (tuple(str(part) for part in error.path), error.message),
        )
        for error in errors:
            for field in _finding_fields(error):
                rule = f'{rule_namespace}.{field}' if field else f'{rule_namespace}.frontmatter'
                findings.append(
                    Finding(
                        path=ref.path,
                        line=_key_line(frontmatter, field) if field else _FIRST_LINE,
                        rule=rule,
                        message=f'{error.message} (per {aspect.path})',
                    )
                )

    return HeaderCheckResult(findings=tuple(findings))


def _one_finding(ref: DocumentRef, rule: str, message: str) -> HeaderCheckResult:
    """The result of a document whose frontmatter is unusable: one finding on its first line."""
    return HeaderCheckResult(findings=(Finding(path=ref.path, line=_FIRST_LINE, rule=rule, message=message),))


def _key_line(frontmatter: Frontmatter, key: str) -> LineNumber:
    """The line a top-level key is written on, or line 1 when the frontmatter does not have it."""
    line = frontmatter.key_line(key)
    if line is None:
        return _FIRST_LINE
    return line


def _finding_fields(error: ValidationError) -> list[str]:
    """Return the top-level fields implicated by one schema error."""
    if error.path:
        return [str(error.path[0])]

    if error.validator == 'required' and isinstance(error.instance, dict):
        return [str(field) for field in error.validator_value if field not in error.instance]

    return ['']
