"""Check one document's section structure against the structure specifications that govern it.

The check is pure: it takes the document's headings, its ref and the already validated structure aspects,
and returns findings. It reads the headings and nothing else, so it is handed those rather than the whole parse
tree. It covers the mechanical half of a specification's section rules: the H1 title, empty
sections, forbidden sections, and the order of the sections the outline names. Whether a section says what it
should is a judgment call, and stays with review.

Each aspect is applied on its own. A namespace specification states only what it adds to the corpus one, so
a document governed by both must pass both, and neither can relax the other.
"""

from dataclasses import dataclass
from typing import Final

from lorecraft_project.document import DocumentRef
from lorecraft_project.schemas import AnySections, StructureAspect
from lorecraft_project.syntax import Heading, LineNumber

from .reporting import Finding

_SECTION_LEVEL: Final[int] = 2
"""The heading level of a section: H1 is the title, and anything deeper is a subsection."""

_FIRST_LINE: Final[LineNumber] = LineNumber(1)
"""Where a finding about the document as a whole is reported: a missing title, a missing section."""


@dataclass(frozen=True, slots=True)
class StructureCheckResult:
    """What the structure check found in one document.

    Attributes:
        findings: Ordered by line, then rule; empty when the document conforms.
    """

    findings: tuple[Finding, ...]


@dataclass(frozen=True, slots=True)
class _Violation:
    """One broken rule, before the aspect that states it and the document it is in are attached."""

    line: LineNumber
    rule: str
    message: str


def validate_structure(
    headings: tuple[Heading, ...], ref: DocumentRef, aspects: tuple[StructureAspect, ...]
) -> StructureCheckResult:
    """Check one document's headings against the structure aspects that govern it.

    Every finding's message ends by quoting the aspect's ``authority``, so a reader is sent to the prose rule.

    Args:
        headings: The document's top-level headings, in document order, as its parse tree holds them.
        ref: The document; its path is every finding's path.
        aspects: Applied each on its own. Empty means the document is ungoverned, which yields no findings.
    """
    sections = tuple(heading for heading in headings if heading.level == _SECTION_LEVEL)
    findings: list[Finding] = []
    for aspect in aspects:
        violations = [
            *_check_title(aspect, headings),
            *_check_empty(aspect, headings),
            *_check_forbidden(aspect, sections),
            *_check_outline(aspect, sections),
        ]
        for violation in violations:
            findings.append(
                Finding(
                    path=ref.path,
                    line=violation.line,
                    rule=violation.rule,
                    message=f'{violation.message} (per {aspect.authority})',
                )
            )
    findings.sort(key=lambda finding: (finding.line.value, finding.rule))
    return StructureCheckResult(findings=tuple(findings))


def _check_title(aspect: StructureAspect, headings: tuple[Heading, ...]) -> list[_Violation]:
    """Check the number of H1 titles, and that one opens the document when the aspect requires it."""
    if aspect.title is None:
        return []
    violations: list[_Violation] = []
    titles = [heading for heading in headings if heading.level == 1]
    if len(titles) != aspect.title.count:
        violations.append(
            _Violation(_FIRST_LINE, 'structure.title', f'expected {aspect.title.count} H1 title, found {len(titles)}')
        )
    if aspect.title.first and not (headings and headings[0].level == 1):
        violations.append(_Violation(_FIRST_LINE, 'structure.title', 'the H1 title comes before any section'))
    return violations


def _check_empty(aspect: StructureAspect, headings: tuple[Heading, ...]) -> list[_Violation]:
    """Report every heading whose section holds nothing, when the aspect forbids empty sections."""
    if not aspect.forbid_empty_sections:
        return []
    violations: list[_Violation] = []
    for heading in headings:
        if heading.empty:
            violations.append(
                _Violation(
                    heading.line,
                    'structure.empty',
                    f'section `{heading.text}` is empty; omit it rather than leaving it empty',
                )
            )
    return violations


def _check_forbidden(aspect: StructureAspect, sections: tuple[Heading, ...]) -> list[_Violation]:
    """Report the first occurrence of every section the aspect forbids."""
    violations: list[_Violation] = []
    for name in aspect.forbidden:
        for section in sections:
            if section.text == name:
                violations.append(
                    _Violation(section.line, 'structure.forbidden', f'section `{name}` is forbidden here')
                )
                break
    return violations


def _check_outline(aspect: StructureAspect, sections: tuple[Heading, ...]) -> list[_Violation]:
    """Match the outline against the document's sections, left to right.

    One violation at most: past the first divergence every later entry is measured against sections it was
    never meant to match, and what that cascade reports says nothing.
    """
    if not aspect.outline:
        return []

    named = set(aspect.section_names())
    at = 0  # the first section not yet accounted for

    for entry in aspect.outline:
        if isinstance(entry, AnySections):
            # The run stops at a section the outline names: that section belongs to the entry naming it,
            # wherever in the outline that entry falls.
            while at < len(sections) and sections[at].text not in named:
                at += 1
            continue

        if at < len(sections) and sections[at].text == entry.name:
            at += 1
            continue
        if entry.optional:
            continue

        if at < len(sections):
            found = sections[at]
            return [
                _Violation(found.line, 'structure.outline', f'expected section `{entry.name}`, found `{found.text}`')
            ]
        return [_Violation(_FIRST_LINE, 'structure.outline', f'missing required section `{entry.name}`')]

    if at < len(sections):
        left = sections[at]
        # A leftover the outline names is a section written out of turn; one it does not name is a section
        # written past the point where the document should have ended.
        if left.text in named:
            message = f'section `{left.text}` is out of order'
        else:
            message = f'unexpected section `{left.text}`; the outline ends before it'
        return [_Violation(left.line, 'structure.outline', message)]
    return []
