"""Which outline entry each of a document's sections falls in, for each structure specification that governs it.

A section is aligned to the entry that names it, wherever in the outline that entry sits, or else to the `any` run it
falls in: the first run after the entry naming the last named section before it. A section no entry names and no run
follows is aligned to nothing. The alignment is a fact of the document and its specifications, whether or not the
document follows the outline: `match_outlines` finds where it stops following it by reading the alignment, and every
rule that needs an outline entry of a section reads it too, so no two of them place a section differently.
"""

from dataclasses import dataclass
from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import SECTION_LEVEL, Heading

from .structure import AnySections, OutlineEntry, SectionEntry, StructureSpec


@dataclass(frozen=True, slots=True)
class AlignedSection:
    """One H2 section of a document, and the outline entry it falls in.

    Attributes:
        section: The section's H2 heading.
        entry: The `SectionEntry` that names the section; or the `AnySections` run it falls in, when no entry names
            it; or `None` when no entry names it and no run follows the last named section before it.
        forbidden: Whether the specification lists the section's heading text under `forbidden`. An outline never
            names a forbidden section, so such a section is aligned to a run, or to nothing.
    """

    section: Heading
    entry: OutlineEntry | None
    forbidden: bool

    @property
    def is_named(self) -> bool:
        """Whether an outline entry names the section, as opposed to a run covering it or nothing."""
        match self.entry:
            case SectionEntry():
                return True
            case AnySections() | None:
                return False
            case _:
                assert_never(self.entry)


@dataclass(frozen=True, slots=True)
class OutlineAlignmentSpec:
    """Where each of a document's sections falls in one structure specification's outline.

    Attributes:
        spec: The structure specification file whose outline the sections are aligned to.
        outline: The specification's outline, which the entries of `sections` belong to; empty when it states none.
        sections: The document's H2 sections, in document order, each with its entry. A specification that states
            no outline aligns each section to nothing.
    """

    spec: RootRelativePath
    outline: tuple[OutlineEntry, ...]
    sections: tuple[AlignedSection, ...]

    def find(self, heading: Heading) -> AlignedSection | None:
        """The aligned section a heading opens, or `None` when the heading is no H2 section of the document.

        Args:
            heading: Any heading of the document.
        """
        for aligned in self.sections:
            if aligned.section == heading:
                return aligned
        return None


def align_outlines(
    structure_specs: tuple[StructureSpec, ...], headings: tuple[Heading, ...]
) -> tuple[OutlineAlignmentSpec, ...]:
    """Align a document's sections to the outline of each structure specification. Raises nothing.

    Each specification is aligned on its own: a document governed by a corpus and a namespace specification is
    aligned to both.

    Args:
        structure_specs: The structure specifications that govern the document, in the order they apply; each may
            state no outline.
        headings: The document's top-level headings, of every level, in document order; only its H2 sections are
            aligned.

    Returns:
        One entry per specification, in the order given.
    """
    sections = tuple(heading for heading in headings if heading.level == SECTION_LEVEL)
    return tuple(
        OutlineAlignmentSpec(
            spec=structure_spec.path,
            outline=structure_spec.outline,
            sections=_align_sections(structure_spec, sections),
        )
        for structure_spec in structure_specs
    )


def _align_sections(structure_spec: StructureSpec, sections: tuple[Heading, ...]) -> tuple[AlignedSection, ...]:
    """Align each section to the entry of the specification's outline that names it, or the run it falls in.

    Args:
        structure_spec: The structure specification whose `outline` and `forbidden` names the sections are held to.
        sections: The document's H2 headings, in document order.
    """
    outline = structure_spec.outline
    forbidden_names = {name.value for name in structure_spec.forbidden}
    last_named_at = -1  # the outline index of the last named section passed; -1 before any
    aligned: list[AlignedSection] = []
    for section in sections:
        entry: OutlineEntry | None
        entry_at = _find_section_index(outline, section.text)
        if entry_at is None:
            entry = _find_run(outline, after=last_named_at)
        else:
            last_named_at = entry_at
            entry = outline[entry_at]
        aligned.append(AlignedSection(section=section, entry=entry, forbidden=section.text in forbidden_names))
    return tuple(aligned)


def _find_section_index(outline: tuple[OutlineEntry, ...], name: str) -> int | None:
    """Where in the outline the section entry naming `name` sits, or `None` when no entry names it. Raises nothing.

    Args:
        outline: The entries to search, in outline order.
        name: Heading text of the section to find.
    """
    for index, entry in enumerate(outline):
        match entry:
            case SectionEntry():
                if entry.name.value == name:
                    return index
            case AnySections():
                pass  # a run names no section
            case _:
                assert_never(entry)
    return None


def _find_run(outline: tuple[OutlineEntry, ...], *, after: int) -> AnySections | None:
    """The first `any` run past outline index `after`, or `None` when there is none. Raises nothing.

    Args:
        outline: The entries to search, in outline order.
        after: Outline index of the last named section passed, exclusive; -1 searches from the start.
    """
    for entry in outline[after + 1 :]:
        match entry:
            case AnySections():
                return entry
            case SectionEntry():
                pass  # a section entry covers only its own section
            case _:
                assert_never(entry)
    return None
