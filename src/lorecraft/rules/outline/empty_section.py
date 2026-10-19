"""`OUT004`: a section holds no content, under a structure file that forbids empty sections."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Protocol, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.item import ItemKind
from lorecraft.project.query import GovernancePrimitives, ItemQuery, SyntaxPrimitives, item_parse, item_structure_specs
from lorecraft.project.schemas import (
    AnyRunAlignment,
    NamedAlignment,
    OutlineAlignmentSpec,
    SectionEntry,
    UnalignedSection,
    find_document_title,
    outline_alignment,
)
from lorecraft.project.syntax import Heading, SectionHeading, section_headings
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Subdiagnostic
from lorecraft.rules.subject import Gate, MetaSpecPart, QueriedItemRule, WhenMetaSpec

from .__ruleset__ import GROUP_ID, example_note, spec_note


@dataclass(frozen=True, slots=True)
class EmptyTitle:
    """Marks an empty heading as the document's title: it is never omitted, so it is asked for content."""


@dataclass(frozen=True, slots=True)
class OtherSection:
    """Marks an empty heading as neither the title nor a section the outline requires: it may be omitted."""


# What an empty heading is: the title, a section the outline requires, or any other section.
type SectionRole = EmptyTitle | SectionEntry | OtherSection


@dataclass(frozen=True, slots=True)
class EmptyHeading:
    """A heading that opens an empty section, and what it is.

    Attributes:
        heading: The heading that opens the empty section.
        role: What the heading is: the title, a section the outline requires, or any other section.
    """

    heading: Heading
    role: SectionRole


@dataclass(frozen=True, slots=True)
class EmptySectionFacts:
    """What a rule over empty sections reads of the specifications and the headings.

    Attributes:
        specs: The specifications that govern the document and forbid an empty section, in the order they apply.
        empty: The headings that open an empty section, the title included, in document order, each with its role.
    """

    specs: tuple[RootRelativePath, ...]
    empty: tuple[EmptyHeading, ...]


class _GovernanceSyntaxPrimitives(GovernancePrimitives, SyntaxPrimitives, Protocol):
    """The primitives the queries below read."""

    def query[T](self, query: ItemQuery[T]) -> T:
        """The memoized answer of another query over this item."""
        ...


def empty_section_facts(primitives: _GovernanceSyntaxPrimitives) -> EmptySectionFacts:
    """The specifications that forbid an empty section and the empty headings, each with its role. Raises nothing.

    A query: it reads the item's structure specifications and headings and nothing else.

    Args:
        primitives: The model state of the document.
    """
    specs = tuple(spec.path for spec in primitives.query(item_structure_specs) if spec.forbid_empty_sections)
    headings = primitives.query(item_parse).headings
    document_title = find_document_title(headings)
    title = None if document_title is None else document_title.heading
    sections = {section.line: section for section in section_headings(headings)}
    alignments = primitives.query(outline_alignment)
    return EmptySectionFacts(
        specs=specs,
        empty=tuple(
            EmptyHeading(heading=heading, role=_role_of(alignments, heading, title, sections.get(heading.line)))
            for heading in headings
            if heading.empty
        ),
    )


def _role_of(
    alignments: tuple[OutlineAlignmentSpec, ...],
    heading: Heading,
    title: Heading | None,
    section: SectionHeading | None,
) -> SectionRole:
    """What an empty heading is: the title, a section the outline requires, or any other section.

    Args:
        alignments: The document's sections aligned to the outline of every structure file that governs
            it, in the order they apply.
        heading: The heading of the empty section.
        title: The document's title, or `None` when it has none.
        section: The heading as a section, or `None` when it opens no section: only an H2 does.
    """
    # Compared by line, as two headings never start on the same one.
    if title is not None and heading.line == title.line:
        return EmptyTitle()
    if section is None:
        return OtherSection()
    required = _find_required_entry(alignments, section)
    if required is None:
        return OtherSection()
    return required


def _find_required_entry(alignments: tuple[OutlineAlignmentSpec, ...], section: SectionHeading) -> SectionEntry | None:
    """The first outline entry, across the meta specs, that requires a section.

    The entry may come from a meta spec other than the one that forbids empty sections: a namespace can require
    what its corpus leaves out. `None` comes back when no meta spec aligns the section to an entry that
    requires it.

    Args:
        alignments: The document's sections aligned to the outline of every structure file that governs
            it, in the order they apply.
        section: The heading of the empty section.
    """
    for alignment in alignments:
        aligned = alignment.aligned_section(section)
        match aligned:
            case NamedAlignment():
                if not aligned.entry.optional:
                    return aligned.entry
            case AnyRunAlignment() | UnalignedSection():
                pass  # an `any` run, or nothing, requires no section
            case _:
                assert_never(aligned)
    return None


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class EmptySection(QueriedItemRule[EmptySectionFacts]):
    """A section holds no content, under a structure file that forbids empty sections.

    ## What it does

    Checks for headings whose section holds nothing, in documents whose structure file sets
    `empty_sections` to `"forbidden"`. A section ends at the next heading of the same or a higher level, or at the
    end of the document; a deeper heading opens a subsection, which is content. Every heading counts, whatever its
    level: an empty title and an empty subsection are reported like any other section.

    A document that more than one meta spec governs, such as a corpus and a namespace, is reported once for
    each meta spec that forbids empty sections.

    The help follows the section: under the title it asks for the document's content, under a section the outline
    requires it asks for what the entry describes, with the entry's first example, and under any other it asks to
    omit the section.

    ## Why is this bad?

    An empty section promises content the document does not hold. An agent that reads the heading expects the
    section to answer it, and finds nothing; a placeholder left for later reads the same way.

    ## Example

    `docs/__meta__/guide.spec.json`:

    ```json
    {
      "empty_sections": "forbidden"
    }
    ```

    `docs/guide/setup.md`:

    ```markdown
    # Setup

    ## Install

    ## Run

    Run the toolkit once over the repository.
    ```

    ## Use instead

    Write what the section is for, or omit it:

    ```markdown
    # Setup

    ## Run

    Run the toolkit once over the repository.
    ```

    Attributes:
        spec: The structure file that forbids empty sections.
        section: The text of the heading whose section is empty.
        role: What the empty heading is: `EmptyTitle` for the document's title, its first H1, as a later H1 is not;
            the outline entry that requires it, for an H2 that an outline of a meta spec governing the document
            names without `"optional": true`; or `OtherSection` for any other section.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 4)
    NAME: ClassVar[RuleName] = RuleName('empty-section')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    APPLIES_TO: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: WhenMetaSpec(MetaSpecPart.STRUCTURE),
            ItemKind.SKILL_ENTRYPOINT: WhenMetaSpec(MetaSpecPart.STRUCTURE),
        }
    )

    spec: RootRelativePath
    section: str
    role: SectionRole

    def message(self) -> str:
        """Name the empty section."""
        return f'section `{self.section}` is empty'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the meta spec that forbids empty sections, then give the help that fits the section.

        The title is told to hold the document's content, and a required section to hold what its entry
        describes, followed by the entry's first example when it gives one; any other section may be omitted.
        """
        parts: list[Subdiagnostic] = [spec_note(self.spec)]
        role = self.role
        match role:
            case EmptyTitle():
                parts.append(Help("write the document's content under its title"))
            case SectionEntry():
                if role.description is None:
                    parts.append(Help('write what the section holds'))
                else:
                    parts.append(Help(f'write what the section holds: {role.description}'))
                if role.examples:
                    parts.append(example_note(role.name, role.examples[0]))
            case OtherSection():
                parts.append(Help('omit the section rather than leave it empty'))
            case _:
                assert_never(role)
        return tuple(parts)

    @classmethod
    def query(cls) -> ItemQuery[EmptySectionFacts]:
        """The specifications that forbid empty sections and the empty headings with their roles."""
        return empty_section_facts

    @classmethod
    def judge(cls, facts: EmptySectionFacts, /) -> tuple[Self, ...]:
        """One occurrence, at its heading, for each empty section under each meta spec that forbids them.

        The meta specs are taken in the order they apply, and the headings of each in document order. An H2 the
        meta spec's outline requires carries its entry, for the help to describe.

        Args:
            facts: The meta specs that forbid empty sections and the empty headings, each with its role.
        """
        return tuple(
            cls(spec=spec, line=empty.heading.line, section=empty.heading.text, role=empty.role)
            for spec in facts.specs
            for empty in facts.empty
        )
