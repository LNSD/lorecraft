"""`OUT005`: a section a structure specification forbids appears in the document."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import SECTION_LEVEL, HeadingsInput, HeadingsRule
from lorecraft.rules.location import Subdiagnostic

from .__ruleset__ import GROUP_ID, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class ForbiddenSection(HeadingsRule):
    """A section a structure specification forbids appears in the document.

    ## What it does

    Checks for H2 sections whose heading text is one of the names a document's structure specification lists under
    `forbidden`. Only H2 headings are sections: a title or a deeper heading of the same text is not reported. Every
    occurrence is reported, so a forbidden section written twice is reported twice.

    A document that more than one specification governs, such as a corpus and a namespace, is reported once for
    each specification that forbids the section.

    ## Why is this bad?

    A specification forbids a section because what it would hold belongs elsewhere, or nowhere: a changelog kept in
    the version history, or a history of the document that an agent reads as a current rule. Written anyway, the
    section is read as part of the document.

    ## Example

    `docs/__meta__/guide.structure.json`:

    ```json
    {
      "forbidden": ["Changelog"]
    }
    ```

    `docs/guide/setup.md`:

    ```markdown
    # Setup

    ## Run

    Run the toolkit once over the repository.

    ## Changelog

    Added the run step.
    ```

    ## Use instead

    Remove the section, and keep what it held where the specification places it:

    ```markdown
    # Setup

    ## Run

    Run the toolkit once over the repository.
    ```

    Attributes:
        spec: The structure specification that forbids the section.
        section: The text of the forbidden section's heading.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 5)
    NAME: ClassVar[RuleName] = RuleName('forbidden-section')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    spec: RootRelativePath
    section: str

    def message(self) -> str:
        """Name the forbidden section."""
        return f'section `{self.section}` is forbidden'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification that forbids the section."""
        return (spec_note(self.spec),)

    @classmethod
    def check(cls, subject: HeadingsInput) -> tuple[Self, ...]:
        """One occurrence, at its heading, for each forbidden H2 section under each specification that forbids it.

        Args:
            subject: The document's headings, with what each governing structure specification states over them.
        """
        occurrences: list[Self] = []
        for headings_spec in subject.specs:
            forbidden_names = {name.value for name in headings_spec.forbidden}
            for heading in subject.headings:
                if heading.level == SECTION_LEVEL and heading.text in forbidden_names:
                    occurrences.append(cls(spec=headings_spec.spec, line=heading.line, section=heading.text))
        return tuple(occurrences)
