"""`OUT004`: a section holds no content, under a structure specification that forbids empty sections."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import HeadingsInput, HeadingsRule
from lorecraft.rules.location import Help, Subdiagnostic

from .__ruleset__ import GROUP_ID, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class EmptySection(HeadingsRule):
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

    spec: RootRelativePath
    section: str

    def message(self) -> str:
        """Name the empty section."""
        return f'section `{self.section}` is empty'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification that forbids empty sections, and say to omit the section."""
        return (spec_note(self.spec), Help('omit the section rather than leave it empty'))

    @classmethod
    def check(cls, subject: HeadingsInput) -> tuple[Self, ...]:
        """One occurrence, at its heading, for each empty section under each specification that forbids them.

        Args:
            subject: The document's headings, with what each governing structure specification states over them.
        """
        occurrences: list[Self] = []
        for headings_spec in subject.specs:
            if headings_spec.forbid_empty_sections:
                for heading in subject.headings:
                    if heading.empty:
                        occurrences.append(cls(spec=headings_spec.spec, line=heading.line, section=heading.text))
        return tuple(occurrences)
