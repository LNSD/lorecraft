"""`OUT004`: a section holds no content, under a structure specification that forbids empty sections."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import DocumentContext
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Subdiagnostic
from lorecraft.rules.subject import DocumentRule, Facet

from .__ruleset__ import GROUP_ID, spec_note


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

    ## Why is this bad?

    An empty section promises content the document does not hold. An agent that reads the heading expects the
    section to answer it, and finds nothing; a placeholder left for later reads the same way.

    ## Example

    `docs/__meta__/guide.structure.json`:

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
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 4)
    NAME: ClassVar[RuleName] = RuleName('empty-section')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GOVERNED_BY: ClassVar[Facet] = Facet.STRUCTURE

    spec: RootRelativePath
    section: str

    def message(self) -> str:
        """Name the empty section."""
        return f'section `{self.section}` is empty'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification that forbids empty sections, and say to omit the section."""
        return (spec_note(self.spec), Help('omit the section rather than leave it empty'))

    @classmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """One occurrence, at its heading, for each empty section under each specification that forbids them.

        The specifications are taken in the order they apply, and the headings of each in document order.

        Args:
            subject: The document, governed by a structure specification.
        """
        headings = subject.parse().headings
        occurrences: list[Self] = []
        for structure_spec in subject.specifications().structure_specs():
            if structure_spec.forbid_empty_sections:
                for heading in headings:
                    if heading.empty:
                        occurrences.append(cls(spec=structure_spec.path, line=heading.line, section=heading.text))
        return tuple(occurrences)
