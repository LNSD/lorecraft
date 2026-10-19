"""Which outline entry each of a document's sections falls in, for each structure specification that governs it.

A section is aligned to the entry that names it, wherever in the outline that entry sits, or else to the `any` run it
falls in: the first `any` run after the entry naming the last named section before it. A section no entry names and
no `any` run follows is aligned to nothing. The alignment describes the document and its specifications, whether
or not the document follows the outline: `match_outlines` finds where it stops following it by reading the
alignment, and every rule that needs an outline entry of a section reads it too, so no two of them place a section
differently.
"""

from dataclasses import dataclass
from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import Heading, SectionHeading, section_headings

from .section_name import SectionName
from .structure import AnySections, OutlineEntry, SectionEntry, StructureSpec


@dataclass(frozen=True, slots=True)
class NamedAlignment:
    """One H2 section of a document, and the `SectionEntry` that names it.

    A named section is never forbidden: a structure specification refuses to forbid a section its own outline names.

    Only `_find_named_alignment` builds one, from an entry that already names the section.

    Attributes:
        section: The section's H2 heading.
        entry: The `SectionEntry` whose name is the section's heading text.
    """

    section: SectionHeading
    entry: SectionEntry


@dataclass(frozen=True, slots=True)
class AnyRunAlignment:
    """One H2 section of a document that no entry names, and the `any` run it falls in.

    Attributes:
        section: The section's H2 heading.
        run: The `AnySections` run it falls in: the first one after the entry naming the last named section before it.
        forbidden: Whether the specification lists the section's heading text under `forbidden`. An outline never
            names a forbidden section, so such a section falls in an `any` run or in nothing.
    """

    section: SectionHeading
    run: AnySections
    forbidden: bool


@dataclass(frozen=True, slots=True)
class UnalignedSection:
    """One H2 section of a document that no entry names and no `any` run follows the last named section before.

    Attributes:
        section: The section's H2 heading.
        forbidden: Whether the specification lists the section's heading text under `forbidden`.
    """

    section: SectionHeading
    forbidden: bool


# One H2 section of a document, and the outline entry it falls in: the entry that names it, the `any` run it falls in,
# or nothing.
type AlignedSection = NamedAlignment | AnyRunAlignment | UnalignedSection


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

    def aligned_section(self, section: SectionHeading) -> AlignedSection:
        """The aligned section a section heading opens.

        Args:
            section: An H2 section of the document these sections were aligned for.

        Raises:
            ValueError: If `section` is no section of that document.
        """
        for aligned in self.sections:
            # Compared by line, as two headings never start on the same one.
            if aligned.section.line == section.line:
                return aligned
        raise ValueError(f'the heading at line {section.line} is no section of the aligned document')


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
    sections = section_headings(headings)
    return tuple(
        OutlineAlignmentSpec(
            spec=structure_spec.path,
            outline=structure_spec.outline,
            sections=_align_sections(structure_spec, sections),
        )
        for structure_spec in structure_specs
    )


def _align_sections(structure_spec: StructureSpec, sections: tuple[SectionHeading, ...]) -> tuple[AlignedSection, ...]:
    """Align each section to the entry of the specification's outline that names it, or the `any` run it falls in.

    Args:
        structure_spec: The structure specification whose `outline` and `forbidden` names the sections are held to.
        sections: The document's H2 headings, in document order.
    """
    outline = structure_spec.outline
    forbidden = structure_spec.forbidden
    last_named_at = -1  # the outline index of the last named section passed; -1 before any
    aligned: list[AlignedSection] = []
    for section in sections:
        named = _find_named_alignment(outline, section)
        if named is not None:
            entry_at, alignment = named
            last_named_at = entry_at
            aligned.append(alignment)
            continue
        is_forbidden = _is_forbidden(forbidden, section)
        run = _find_run(outline, after=last_named_at)
        if run is None:
            aligned.append(UnalignedSection(section=section, forbidden=is_forbidden))
        else:
            aligned.append(AnyRunAlignment(section=section, run=run, forbidden=is_forbidden))
    return tuple(aligned)


def _is_forbidden(forbidden: tuple[SectionName, ...], section: SectionHeading) -> bool:
    """Whether one of the forbidden names stands for the section. Raises nothing.

    Args:
        forbidden: The names the specification forbids.
        section: An H2 heading of the document.
    """
    return any(name.is_name_of(section) for name in forbidden)


def _find_named_alignment(
    outline: tuple[OutlineEntry, ...], section: SectionHeading
) -> tuple[int, NamedAlignment] | None:
    """The alignment of `section` to its entry, and where that sits in the outline, or `None` if no entry names it.

    Raises nothing. The entry is checked to name `section` before the alignment is built.

    Args:
        outline: The entries to search, in outline order.
        section: The H2 heading of the section to find.
    """
    for index, entry in enumerate(outline):
        match entry:
            case SectionEntry():
                if entry.is_name_of(section):
                    return index, NamedAlignment(section=section, entry=entry)
            case AnySections():
                pass  # an `any` run names no section
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
