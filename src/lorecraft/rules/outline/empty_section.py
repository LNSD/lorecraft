"""`OUT004`: a section holds no content, under a structure specification that forbids empty sections."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import DocumentContext
from lorecraft.project.schemas import (
    AnyRunAlignment,
    NamedAlignment,
    OutlineAlignmentSpec,
    SectionEntry,
    UnalignedSection,
)
from lorecraft.project.syntax import Heading, find_title
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Subdiagnostic
from lorecraft.rules.subject import DocumentRule, Facet

from .__ruleset__ import GROUP_ID, example_note, spec_note


def _find_required_entry(alignments: tuple[OutlineAlignmentSpec, ...], heading: Heading) -> SectionEntry | None:
    """The first outline entry, across the specifications, that requires the section a heading opens.

    Only an H2 is a section an outline aligns. The entry may come from a specification other than the one that
    forbids empty sections: a namespace can require what its corpus leaves out. `None` comes back when the heading
    is no H2, or no specification aligns it to an entry that requires it.

    Args:
        alignments: The document's sections aligned to the outline of every structure specification that governs
            it, in the order they apply.
        heading: The heading of the empty section.
    """
    for alignment in alignments:
        aligned = alignment.find(heading)
        if aligned is None:
            continue
        match aligned:
            case NamedAlignment():
                if not aligned.entry.optional:
                    return aligned.entry
            case AnyRunAlignment() | UnalignedSection():
                pass  # an `any` run, or nothing, requires no section
            case _:
                assert_never(aligned)
    return None


@dataclass(frozen=True, slots=True)
class EmptyTitle:
    """Marks an empty heading as the document's title: it is never omitted, so it is asked for content."""


@dataclass(frozen=True, slots=True)
class OtherSection:
    """Marks an empty heading as neither the title nor a section the outline requires: it may be omitted."""


def _role_of(
    alignments: tuple[OutlineAlignmentSpec, ...], heading: Heading, title: Heading | None
) -> EmptyTitle | SectionEntry | OtherSection:
    """What an empty heading is: the title, a section the outline requires, or any other section.

    Args:
        alignments: The document's sections aligned to the outline of every structure specification that governs
            it, in the order they apply.
        heading: The heading of the empty section.
        title: The document's title, or `None` when it has none.
    """
    # Compared by line, as two headings never start on the same one.
    if title is not None and heading.line == title.line:
        return EmptyTitle()
    required = _find_required_entry(alignments, heading)
    if required is None:
        return OtherSection()
    return required


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class EmptySection(DocumentRule):
    """A section holds no content, under a structure specification that forbids empty sections.

    ## What it does

    Checks for headings whose section holds nothing, in documents whose structure specification sets
    `empty_sections` to `"forbidden"`. A section ends at the next heading of the same or a higher level, or at the
    end of the document; a deeper heading opens a subsection, which is content. Every heading counts, whatever its
    level: an empty title and an empty subsection are reported like any other section.

    A document that more than one specification governs, such as a corpus and a namespace, is reported once for
    each specification that forbids empty sections.

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
        spec: The structure specification that forbids empty sections.
        section: The text of the heading whose section is empty.
        role: What the empty heading is: `EmptyTitle` for the document's title, its first H1, as a later H1 is not;
            the outline entry that requires it, for an H2 that an outline of a specification governing the document
            names without `"optional": true`; or `OtherSection` for any other section.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 4)
    NAME: ClassVar[RuleName] = RuleName('empty-section')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GOVERNED_BY: ClassVar[Facet] = Facet.STRUCTURE

    spec: RootRelativePath
    section: str
    role: EmptyTitle | SectionEntry | OtherSection

    def message(self) -> str:
        """Name the empty section."""
        return f'section `{self.section}` is empty'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification that forbids empty sections, then give the help that fits the section.

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
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """One occurrence, at its heading, for each empty section under each specification that forbids them.

        The specifications are taken in the order they apply, and the headings of each in document order. An H2 the
        specification's outline requires carries its entry, for the help to describe.

        Args:
            subject: The document, governed by a structure specification.
        """
        headings = subject.parse().headings
        title = find_title(headings)
        alignments = subject.outline_alignment()
        occurrences: list[Self] = []
        for structure_spec in subject.specifications().structure_specs():
            if structure_spec.forbid_empty_sections:
                for heading in headings:
                    if heading.empty:
                        occurrences.append(
                            cls(
                                spec=structure_spec.path,
                                line=heading.line,
                                section=heading.text,
                                role=_role_of(alignments, heading, title),
                            )
                        )
        return tuple(occurrences)
