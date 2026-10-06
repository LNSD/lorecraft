"""`OUT007`: a section the outline names is written out of the order the outline sets."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import DocumentContext
from lorecraft.project.schemas import AbsentSection, MisplacedSection, SectionName, UnlistedSection
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Here, Label, Subdiagnostic
from lorecraft.rules.subject import DocumentRule, Facet

from .__ruleset__ import GROUP_ID, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class SectionOutOfOrder(DocumentRule):
    """A section the outline names is written out of the order the outline sets.

    ## What it does

    Checks for documents that write a section their structure specification lists under its `outline` key in a
    place the outline gives to a different section. The section is reported where it stands, which is either
    where the outline expects a section the document only writes further down, or after every section the
    outline matched, once nothing in the outline is left to place it.

    Only the first place a document stops following its outline is reported, since every section after it is
    compared with an entry it was never meant to match. A document that more than one specification governs, such
    as a corpus and a namespace, must follow each outline, and is reported once for each it breaks.

    ## Why is this bad?

    An agent that loads the document expects every document of its kind to answer the same questions in the same
    order; a section out of its place is read before the sections it builds on, or missed by an agent that stops
    reading where it expects the section to be.

    ## Example

    `docs/__meta__/guide.structure.json`:

    ```json
    {
      "outline": [
        {"section": "Usage"},
        {"section": "Options"}
      ]
    }
    ```

    `docs/guide/check.md`:

    ```markdown
    # Check

    ## Options

    `--strict` fails on a warning.

    ## Usage

    Run `lorecraft check` from the repository root.
    ```

    ## Use instead

    Write the sections in the order the outline lists them:

    ```markdown
    # Check

    ## Usage

    Run `lorecraft check` from the repository root.

    ## Options

    `--strict` fails on a warning.
    ```

    Attributes:
        spec: The structure specification whose outline sets the order.
        section: The heading text of the section written out of order, which the occurrence is reported at.
        expected: The section the outline places there instead, which the document writes further down; or
            `None` when the section is left over after every section the outline matched.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 7)
    NAME: ClassVar[RuleName] = RuleName('section-out-of-order')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GOVERNED_BY: ClassVar[Facet] = Facet.OUTLINE

    spec: RootRelativePath
    section: str
    expected: SectionName | None

    def message(self) -> str:
        """Name the section written out of order."""
        return f'section `{self.section}` is out of order'

    def labels(self) -> tuple[Label, ...]:
        """Mark the section, with the section the outline places there instead, or that none is left to place it."""
        if self.expected is None:
            return (Label(Here(self.line), 'left over after every section the outline matched'),)
        return (Label(Here(self.line), f'expected `{self.expected}` here'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification whose outline sets the order."""
        return (spec_note(self.spec),)

    @classmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """One occurrence for each outline whose first divergence is a section it names, out of its place.

        Args:
            subject: The document, governed by at least one outline.
        """
        occurrences: list[Self] = []
        for outline_spec in subject.outline_divergences():
            divergence = outline_spec.divergence
            match divergence:
                case MisplacedSection():
                    occurrences.append(
                        cls(
                            spec=outline_spec.spec,
                            line=divergence.section.line,
                            section=divergence.section.text,
                            expected=divergence.expected,
                        )
                    )
                case AbsentSection() | UnlistedSection() | None:
                    pass  # the document matches the outline, or diverges from it otherwise
                case _:
                    assert_never(divergence)
        return tuple(occurrences)
