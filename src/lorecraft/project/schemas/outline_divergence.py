"""Where a document's sections first stop matching the outline a structure specification states.

The outline is matched against the document's H2 sections left to right, and matching stops at the first
divergence: a required section absent from the document, a named section out of its place, or a section the outline
does not name. Every later entry would be compared with sections it was never meant to match, so what that cascade
finds says nothing.
"""

from dataclasses import dataclass
from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineCount, LineNumber, SectionHeading

from .outline_alignment import AlignedSection, AnyRunAlignment, NamedAlignment, OutlineAlignmentSpec, UnalignedSection
from .section_name import SectionName
from .structure import AnySections, OutlineEntry, SectionEntry


@dataclass(frozen=True, slots=True)
class DocumentEnd:
    """The end of a document, where a section the outline expects last would be written.

    Attributes:
        last_line: The document's last line, or line 1 for an empty document.
        after: The document's last H2 section, which a section expected at the end would follow; or `None` when
            the document holds no H2 section.
    """

    last_line: LineNumber
    after: SectionHeading | None


@dataclass(frozen=True, slots=True)
class AbsentSection:
    """A required section the outline expects next, which the document holds nowhere.

    Attributes:
        name: The section's heading text, as the outline entry names it.
        description: What the section holds, as the outline entry states it, or `None` when it states none.
        example: The first sample of the section's body the outline entry gives, without its heading, or `None`
            when it gives none.
        before: The section found where the missing one was expected, which it should come before; or the end of
            the document, when every section was matched before the outline expected it.
    """

    name: SectionName
    description: str | None
    example: str | None
    before: SectionHeading | DocumentEnd


@dataclass(frozen=True, slots=True)
class ExpectedSection:
    """The section the outline places where another stands, which the document holds later.

    Attributes:
        name: The section's heading text, as the outline entry names it.
        written_at: The heading where the document writes it, after the section standing in its place.
    """

    name: SectionName
    written_at: SectionHeading


@dataclass(frozen=True, slots=True)
class LeftOver:
    """A section the outline names, left once the outline is used up.

    Attributes:
        earlier: The heading of the same text the outline matched before, when the section is written twice; or
            `None` when this is its only heading, an optional section the document skipped and wrote late.
    """

    earlier: SectionHeading | None


@dataclass(frozen=True, slots=True)
class OutlineEnd:
    """The end of the outline, past which the document still writes a section.

    Attributes:
        last_matched: The last section the outline matched or skipped over, or `None` when it matched none.
    """

    last_matched: SectionHeading | None


@dataclass(frozen=True, slots=True)
class MisplacedSection:
    """A section the outline names, written where the outline places a different section.

    Attributes:
        section: The section's H2 heading.
        placement: The section the outline places there instead, which the document holds later; or the section
            left over once the outline is used up.
    """

    section: SectionHeading
    placement: ExpectedSection | LeftOver


@dataclass(frozen=True, slots=True)
class UnlistedSection:
    """A section the outline does not name, in a place no `any` run of the outline covers.

    Attributes:
        section: The section's H2 heading.
        placement: The section the outline places there instead, which the document holds later; or the end of
            the outline, when the section comes after it.
    """

    section: SectionHeading
    placement: ExpectedSection | OutlineEnd


# The first place a document's sections stop matching an outline: a required section absent from the document, a
# named section out of its place, or a section the outline does not name. Matching stops there, since every later
# entry would be compared with sections it was never meant to match.
type OutlineDivergence = AbsentSection | MisplacedSection | UnlistedSection


@dataclass(frozen=True, slots=True)
class OutlineDivergenceSpec:
    """Where a document's sections first stop matching one structure specification's outline.

    Attributes:
        spec: The structure specification file whose outline the sections are matched against.
        divergence: The first divergence, or `None` when the sections match the outline.
    """

    spec: RootRelativePath
    divergence: OutlineDivergence | None


def match_outlines(
    alignments: tuple[OutlineAlignmentSpec, ...], line_count: LineCount
) -> tuple[OutlineDivergenceSpec, ...]:
    """Find where a document's aligned sections first stop matching each outline, in the alignments given.

    Each outline is matched on its own: a document governed by a corpus and a namespace specification that both
    state an outline must match both. An alignment of a specification that states no outline has nothing to match,
    so it has no entry in the result. Raises nothing.

    Args:
        alignments: The document's sections aligned to each governing structure specification, in the order the
            specifications apply, as `align_outlines` returns them.
        line_count: The lines in the document's whole file, where a section expected after every other one is
            placed; 0 for an empty document.

    Returns:
        One entry per alignment whose specification states an outline, in the order given.
    """
    specs: list[OutlineDivergenceSpec] = []
    for alignment in alignments:
        if not alignment.outline:
            continue
        sections = alignment.sections
        # An empty document has no line at all, so its end is reported on line 1. A count is never negative, so
        # `from_int` cannot raise here.
        document_end = DocumentEnd(
            last_line=LineNumber.from_int(max(line_count.value, 1)), after=sections[-1].section if sections else None
        )
        divergence = _first_divergence(alignment.outline, sections, document_end)
        specs.append(OutlineDivergenceSpec(spec=alignment.spec, divergence=divergence))
    return tuple(specs)


def _is_named(aligned: AlignedSection) -> bool:
    """Whether an outline entry names the section, as opposed to an `any` run covering it or nothing.

    Args:
        aligned: The section whose alignment kind determines whether an outline entry names it.
    """
    match aligned:
        case NamedAlignment():
            return True
        case AnyRunAlignment() | UnalignedSection():
            return False
        case _:
            assert_never(aligned)


def _first_divergence(
    outline: tuple[OutlineEntry, ...], aligned: tuple[AlignedSection, ...], document_end: DocumentEnd
) -> OutlineDivergence | None:
    """Match the outline against the document's sections, left to right, and return where they first diverge.

    One divergence at most: past the first, every later entry is measured against sections it was never meant to
    match, and what that cascade finds says nothing. Whether the outline names a section is read from the alignment,
    so this walk and every rule reading the alignment agree on it. Raises nothing.

    Args:
        outline: The outline that is matched; the specification states one.
        aligned: The document's H2 sections, in document order, each with the entry it is aligned to.
        document_end: Where a section expected after every section of the document should be written.

    Returns:
        The first divergence, or `None` when the sections match the outline.
    """
    at = 0  # the first section not yet accounted for

    for entry in outline:
        match entry:
            case AnySections():
                # The `any` run stops at a section the outline names: that section belongs to the entry naming it,
                # wherever in the outline that entry falls.
                while at < len(aligned) and not _is_named(aligned[at]):
                    at += 1
            case SectionEntry():
                if at < len(aligned) and entry.names(aligned[at].section):
                    at += 1
                    continue
                if entry.optional:
                    continue
                return _divergence_at_entry(entry, aligned, at, document_end)
            case _:
                assert_never(entry)

    if at < len(aligned):
        # A leftover the outline names is a section written out of turn; one it does not name is a section written
        # past the point where the document should have ended.
        left = aligned[at].section
        if _is_named(aligned[at]):
            earlier = next((a.section for a in aligned[:at] if a.section.text == left.text), None)
            return MisplacedSection(section=left, placement=LeftOver(earlier=earlier))
        last_matched = aligned[at - 1].section if at > 0 else None
        return UnlistedSection(section=left, placement=OutlineEnd(last_matched=last_matched))
    return None


def _divergence_at_entry(
    entry: SectionEntry, aligned: tuple[AlignedSection, ...], at: int, document_end: DocumentEnd
) -> OutlineDivergence:
    """The divergence found where a required outline entry does not match the next section. Raises nothing.

    When the document holds the expected section nowhere, it is missing, and should come before the section found
    in its place, or at the end of the document. When it holds it later, the section found in its place is the one
    that diverges: out of order if the outline names it, unexpected if not.

    Args:
        entry: The required outline entry the next section does not match.
        aligned: The document's H2 sections, in document order, each with the entry it is aligned to.
        at: The index of the first section not yet accounted for; `len(aligned)` when every one is.
        document_end: Where a section expected after every section of the document should be written.
    """
    # Every section before `at` was matched by its own entry or skipped by an `any` run, which skips no named
    # section, so searching the whole document finds the expected section only at `at` or later.
    held = next((a.section for a in aligned if entry.names(a.section)), None)
    if held is None:
        before = aligned[at].section if at < len(aligned) else document_end
        example = entry.examples[0] if entry.examples else None
        return AbsentSection(name=entry.name, description=entry.description, example=example, before=before)

    # The expected section is held later, so a section stands in its place.
    found = aligned[at]
    expected = ExpectedSection(name=entry.name, written_at=held)
    if _is_named(found):
        return MisplacedSection(section=found.section, placement=expected)
    return UnlistedSection(section=found.section, placement=expected)
