"""Check one document's section structure against the structure specifications that govern it.

The check is pure: it takes the already validated structure specifications that govern a document and the
document's headings, and returns violations. It reads those and nothing else, so it is handed them rather than the
whole parse tree, and not even the document's path: the run that called it attaches that. It covers the mechanical
half of a specification's section rules: the H1 title, empty sections, forbidden sections, the order of the sections
the outline names, and the word cap on each section. Whether a section says what it should is a judgment call, and
stays with review. A section the outline expects but the document lacks is reported with the notes its entry
states: help with its description, and a note with its first example.

Each structure specification is applied on its own. A namespace specification states only what it adds to the
corpus one, so a document governed by both must pass both, and neither can relax the other.
"""

from dataclasses import dataclass
from typing import Final, assert_never

from lorecraft.project.schemas import AnySections, OutlineEntry, SectionEntry, StructureSpec
from lorecraft.project.syntax import Heading, LineNumber

from .reporting import Note, NoteKind, Violation

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


def validate_structure(
    structure_specs: tuple[StructureSpec, ...], *, headings: tuple[Heading, ...]
) -> StructureCheckResult:
    """Check one document's headings against the structure specifications that govern it.

    Every violation's message ends by quoting the structure specification's `authority`, so a reader is sent to the
    prose rule.

    Args:
        structure_specs: Applied each on its own. Empty means the document is ungoverned, which yields no violations.
        headings: The document's top-level headings, in document order, as its parse tree holds them.
    """
    sections = tuple(heading for heading in headings if heading.level == _SECTION_LEVEL)
    violations: list[Violation] = []
    for structure_spec in structure_specs:
        spec_violations = [
            *_check_title(structure_spec, headings),
            *_check_empty(structure_spec, headings),
            *_check_forbidden(structure_spec, sections),
            *_check_outline(structure_spec, sections),
            *_check_section_words(structure_spec, sections),
        ]
        for violation in spec_violations:
            message = f'{violation.message} (per {structure_spec.authority})'
            violations.append(
                Violation(
                    line=violation.line,
                    rule=violation.rule,
                    message=message,
                    spec=structure_spec.path,
                    notes=violation.notes,
                )
            )
    violations.sort(key=lambda violation: (violation.line.value, violation.rule))
    return StructureCheckResult(violations=tuple(violations))


def _check_title(structure_spec: StructureSpec, headings: tuple[Heading, ...]) -> list[Violation]:
    """Check the number of H1 titles, and that one opens the document when the structure specification requires it.

    Args:
        structure_spec: The structure specification whose `title` rule applies; one without a `title` yields no
            violation.
        headings: Every heading of the document, in document order, of any level.
    """
    if structure_spec.title is None:
        return []
    violations: list[Violation] = []
    titles = [heading for heading in headings if heading.level == 1]
    if len(titles) != structure_spec.title.count:
        violations.append(
            Violation(
                _FIRST_LINE, 'structure.title', f'expected {structure_spec.title.count} H1 title, found {len(titles)}'
            )
        )
    if structure_spec.title.first and not (headings and headings[0].level == 1):
        violations.append(Violation(_FIRST_LINE, 'structure.title', 'the H1 title comes before any section'))
    return violations


def _check_empty(structure_spec: StructureSpec, headings: tuple[Heading, ...]) -> list[Violation]:
    """Report every heading whose section holds nothing, when the structure specification forbids empty sections.

    Args:
        structure_spec: The structure specification; with `forbid_empty_sections` off nothing is reported.
        headings: Every heading of the document, of any level; the title and subsections included.
    """
    if not structure_spec.forbid_empty_sections:
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


def _check_forbidden(structure_spec: StructureSpec, sections: tuple[Heading, ...]) -> list[Violation]:
    """Report the first occurrence of every section the structure specification forbids.

    Args:
        structure_spec: The structure specification whose `forbidden` names are looked for.
        sections: The document's H2 headings, in document order.
    """
    violations: list[Violation] = []
    for name in structure_spec.forbidden:
        for section in sections:
            if section.text == name:
                violations.append(Violation(section.line, 'structure.forbidden', f'section `{name}` is forbidden here'))
                break
    return violations


def _check_outline(structure_spec: StructureSpec, sections: tuple[Heading, ...]) -> list[Violation]:
    """Match the outline against the document's sections, left to right.

    One violation at most: past the first divergence every later entry is measured against sections it was
    never meant to match, and what that cascade reports says nothing.

    Args:
        structure_spec: The structure specification whose `outline` is matched; an empty outline yields no violation.
        sections: The document's H2 headings, in document order.
    """
    if not structure_spec.outline:
        return []

    named = set(structure_spec.section_names())
    at = 0  # the first section not yet accounted for

    for entry in structure_spec.outline:
        match entry:
            case AnySections():
                # The run stops at a section the outline names: that section belongs to the entry naming it,
                # wherever in the outline that entry falls.
                while at < len(sections) and sections[at].text not in named:
                    at += 1
            case SectionEntry():
                if at < len(sections) and sections[at].text == entry.name:
                    at += 1
                    continue
                if entry.optional:
                    continue

                notes = _missing_section_notes(entry)
                if at < len(sections):
                    found = sections[at]
                    return [
                        Violation(
                            found.line,
                            'structure.outline',
                            f'expected section `{entry.name}`, found `{found.text}`',
                            notes=notes,
                        )
                    ]
                return [
                    Violation(_FIRST_LINE, 'structure.outline', f'missing required section `{entry.name}`', notes=notes)
                ]
            case _:
                assert_never(entry)

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


def _missing_section_notes(entry: SectionEntry) -> tuple[Note, ...]:
    """The notes telling the author of a document that lacks a section what to write there.

    Help with the entry's description, then a note with its first example, written out under the section's heading
    as it would sit in the document; each only when the entry states it. Any further examples are for a reader of
    the specification, not repeated on every finding.

    Args:
        entry: The outline entry naming the section the document lacks.
    """
    notes: list[Note] = []
    if entry.description is not None:
        notes.append(Note(NoteKind.HELP, entry.description))
    if entry.examples:
        first_example = entry.examples[0]
        notes.append(Note(NoteKind.NOTE, f'for example:\n## {entry.name}\n\n{first_example}'))
    return tuple(notes)


def _check_section_words(structure_spec: StructureSpec, sections: tuple[Heading, ...]) -> list[Violation]:
    """Report every section holding more prose words than its outline entry allows, its subsections included.

    A section the outline names takes the cap of the entry naming it, which may be none. Any other section takes
    the cap of the `any` run it falls in: the first `any` entry after the entry naming the last named section
    before it. In a document that follows the outline, that is the run which matches it.

    Args:
        structure_spec: The structure specification whose `outline` entries carry the word caps.
        sections: The document's H2 headings, in document order, each with its prose word count.
    """
    violations: list[Violation] = []
    last_named_at = -1  # the outline index of the last named section passed; -1 before any
    for section in sections:
        entry_at = _find_entry_index(structure_spec.outline, section.text)
        if entry_at is None:
            cap = _find_run_cap(structure_spec.outline, last_named_at)
        else:
            last_named_at = entry_at
            cap = structure_spec.outline[entry_at].words
        if cap is not None and section.words > cap:
            violations.append(
                Violation(
                    section.line,
                    'structure.words.section',
                    f'section `{section.text}` is {section.words} prose words; the cap is {cap}',
                )
            )
    return violations


def _find_entry_index(outline: tuple[OutlineEntry, ...], name: str) -> int | None:
    """Where in the outline the section entry naming `name` sits, or None when no entry names it.

    Args:
        outline: The entries to search, in outline order.
        name: Heading text of the section to find.
    """
    for index, entry in enumerate(outline):
        match entry:
            case SectionEntry():
                if entry.name == name:
                    return index
            case AnySections():
                pass  # a run names no section
            case _:
                assert_never(entry)
    return None


def _find_run_cap(outline: tuple[OutlineEntry, ...], after: int) -> int | None:
    """The cap of the first `any` entry past outline index `after`, or None when there is no such entry.

    Args:
        outline: The entries to search, in outline order.
        after: Outline index of the last named section passed, exclusive; -1 searches from the start.
    """
    for entry in outline[after + 1 :]:
        match entry:
            case AnySections():
                return entry.words
            case SectionEntry():
                pass  # a section entry caps only its own section
            case _:
                assert_never(entry)
    return None
