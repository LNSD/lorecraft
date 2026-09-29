"""Check one document's section structure against the structure specifications that govern it.

The check is pure: it takes the already validated structure aspects that govern a document and the document's
headings, and returns violations. It reads those and nothing else, so it is handed them rather than the whole parse
tree, and not even the document's path: the run that called it attaches that. It covers the mechanical half of a
specification's section rules: the H1 title, empty sections, forbidden sections, the order of the sections the
outline names, and the word cap on each section. Whether a section
says what it should is a judgment call, and stays with review.

Each aspect is applied on its own. A namespace specification states only what it adds to the corpus one, so
a document governed by both must pass both, and neither can relax the other.
"""

from dataclasses import dataclass
from typing import Final

from lorecraft.project.schemas import AnySections, OutlineEntry, SectionEntry, StructureAspect
from lorecraft.project.syntax import Heading, LineNumber

from .reporting import Violation

_SECTION_LEVEL: Final[int] = 2
"""The heading level of a section: H1 is the title, and anything deeper is a subsection."""

_FIRST_LINE: Final[LineNumber] = LineNumber(1)
"""Where a violation of the document as a whole is reported: a missing title, a missing section."""


@dataclass(frozen=True, slots=True)
class StructureCheckResult:
    """What the structure check found in one document.

    Attributes:
        violations: Ordered by line, then rule; empty when the document conforms.
    """

    violations: tuple[Violation, ...]


def validate_structure(aspects: tuple[StructureAspect, ...], *, headings: tuple[Heading, ...]) -> StructureCheckResult:
    """Check one document's headings against the structure aspects that govern it.

    Every violation's message ends by quoting the aspect's ``authority``, so a reader is sent to the prose rule.

    Args:
        aspects: Applied each on its own. Empty means the document is ungoverned, which yields no violations.
        headings: The document's top-level headings, in document order, as its parse tree holds them.
    """
    sections = tuple(heading for heading in headings if heading.level == _SECTION_LEVEL)
    violations: list[Violation] = []
    for aspect in aspects:
        aspect_violations = [
            *_check_title(aspect, headings),
            *_check_empty(aspect, headings),
            *_check_forbidden(aspect, sections),
            *_check_outline(aspect, sections),
            *_check_section_words(aspect, sections),
        ]
        for violation in aspect_violations:
            message = f'{violation.message} (per {aspect.authority})'
            violations.append(Violation(line=violation.line, rule=violation.rule, message=message, spec=aspect.path))
    violations.sort(key=lambda violation: (violation.line.value, violation.rule))
    return StructureCheckResult(violations=tuple(violations))


def _check_title(aspect: StructureAspect, headings: tuple[Heading, ...]) -> list[Violation]:
    """Check the number of H1 titles, and that one opens the document when the aspect requires it."""
    if aspect.title is None:
        return []
    violations: list[Violation] = []
    titles = [heading for heading in headings if heading.level == 1]
    if len(titles) != aspect.title.count:
        violations.append(
            Violation(_FIRST_LINE, 'structure.title', f'expected {aspect.title.count} H1 title, found {len(titles)}')
        )
    if aspect.title.first and not (headings and headings[0].level == 1):
        violations.append(Violation(_FIRST_LINE, 'structure.title', 'the H1 title comes before any section'))
    return violations


def _check_empty(aspect: StructureAspect, headings: tuple[Heading, ...]) -> list[Violation]:
    """Report every heading whose section holds nothing, when the aspect forbids empty sections."""
    if not aspect.forbid_empty_sections:
        return []
    violations: list[Violation] = []
    for heading in headings:
        if heading.empty:
            violations.append(
                Violation(
                    heading.line,
                    'structure.empty',
                    f'section `{heading.text}` is empty; omit it rather than leaving it empty',
                )
            )
    return violations


def _check_forbidden(aspect: StructureAspect, sections: tuple[Heading, ...]) -> list[Violation]:
    """Report the first occurrence of every section the aspect forbids."""
    violations: list[Violation] = []
    for name in aspect.forbidden:
        for section in sections:
            if section.text == name:
                violations.append(Violation(section.line, 'structure.forbidden', f'section `{name}` is forbidden here'))
                break
    return violations


def _check_outline(aspect: StructureAspect, sections: tuple[Heading, ...]) -> list[Violation]:
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
                Violation(found.line, 'structure.outline', f'expected section `{entry.name}`, found `{found.text}`')
            ]
        return [Violation(_FIRST_LINE, 'structure.outline', f'missing required section `{entry.name}`')]

    if at < len(sections):
        left = sections[at]
        # A leftover the outline names is a section written out of turn; one it does not name is a section
        # written past the point where the document should have ended.
        if left.text in named:
            message = f'section `{left.text}` is out of order'
        else:
            message = f'unexpected section `{left.text}`; the outline ends before it'
        return [Violation(left.line, 'structure.outline', message)]
    return []


def _check_section_words(aspect: StructureAspect, sections: tuple[Heading, ...]) -> list[Violation]:
    """Report every section holding more prose words than its outline entry allows, its subsections included.

    A section the outline names takes the cap of the entry naming it, which may be none. Any other section takes
    the cap of the ``any`` run it falls in: the first ``any`` entry after the entry naming the last named section
    before it. In a document that follows the outline, that is the run which matches it.
    """
    violations: list[Violation] = []
    last_named_at = -1  # the outline index of the last named section passed; -1 before any
    for section in sections:
        entry_at = _entry_index(aspect.outline, section.text)
        if entry_at is None:
            cap = _run_cap(aspect.outline, last_named_at)
        else:
            last_named_at = entry_at
            cap = aspect.outline[entry_at].words
        if cap is not None and section.words > cap:
            violations.append(
                Violation(
                    section.line,
                    'structure.words.section',
                    f'section `{section.text}` is {section.words} prose words; the cap is {cap}',
                )
            )
    return violations


def _entry_index(outline: tuple[OutlineEntry, ...], name: str) -> int | None:
    """Where in the outline the section entry naming ``name`` sits, or None when no entry names it."""
    for index, entry in enumerate(outline):
        if isinstance(entry, SectionEntry) and entry.name == name:
            return index
    return None


def _run_cap(outline: tuple[OutlineEntry, ...], after: int) -> int | None:
    """The cap of the first ``any`` entry past outline index ``after``, or None when there is no such entry."""
    for entry in outline[after + 1 :]:
        if isinstance(entry, AnySections):
            return entry.words
    return None
