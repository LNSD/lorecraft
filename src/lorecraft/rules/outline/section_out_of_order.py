"""`OUT007`: a section the outline names is written out of the order the outline sets."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import DocumentContext
from lorecraft.project.schemas import AbsentSection, ExpectedSection, LeftOver, MisplacedSection, UnlistedSection
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
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
        placement: The section the outline places there instead, with the heading where the document writes it
            further down; or the section left over after every section the outline matched, with the heading it
            repeats when it is written twice.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 7)
    NAME: ClassVar[RuleName] = RuleName('section-out-of-order')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GOVERNED_BY: ClassVar[Facet] = Facet.OUTLINE

    spec: RootRelativePath
    section: str
    placement: ExpectedSection | LeftOver

    def message(self) -> str:
        """Name the section written out of order."""
        return f'section `{self.section}` is out of order'

    def labels(self) -> tuple[Label, ...]:
        """Mark the section, and where the section the outline places there is written or this one was before.

        A section left over after every section the outline matched has none placed there; a second heading of the
        same text is labelled with the first.
        """
        placement = self.placement
        match placement:
            case ExpectedSection():
                return (
                    Label(Here(self.line), f'expected `{placement.name}` here'),
                    Label(Here(placement.written_at.line), f'`{placement.name}` is written here'),
                )
            case LeftOver():
                labels = [Label(Here(self.line), 'left over after every section the outline matched')]
                if placement.earlier is not None:
                    labels.append(Label(Here(placement.earlier.line), 'already written here'))
                return tuple(labels)
            case _:
                assert_never(placement)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification whose outline sets the order, then say to move the section the outline expects.

        A section left over has none to move, so the specification note is all it gives.
        """
        placement = self.placement
        match placement:
            case ExpectedSection():
                return (spec_note(self.spec), Help(f'move `{placement.name}` above `{self.section}`'))
            case LeftOver():
                return (spec_note(self.spec),)
            case _:
                assert_never(placement)

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
                            placement=divergence.placement,
                        )
                    )
                case AbsentSection() | UnlistedSection() | None:
                    pass  # the document matches the outline, or diverges from it otherwise
                case _:
                    assert_never(divergence)
        return tuple(occurrences)
