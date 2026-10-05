"""`OUT008`: a section the outline does not name, in a place the outline does not allow one."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import SectionName
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import (
    AbsentSection,
    MisplacedSection,
    OutlineDivergenceInput,
    OutlineDivergenceRule,
    UnlistedSection,
)
from lorecraft.rules.location import Here, Label, Subdiagnostic

from .__ruleset__ import GROUP_ID, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class UnexpectedSection(OutlineDivergenceRule):
    """A section the outline does not name, in a place the outline does not allow one.

    ## What it does

    Checks for documents that write a section their structure specification's `outline` does not name, in a place
    no `{"any": true}` entry of the outline covers. The section is reported where it stands, which is either where
    the outline expects a section the document only writes further down, or after the outline's end.

    Only the first place a document stops following its outline is reported, since every section after it is
    compared with an entry it was never meant to match. A document that more than one specification governs, such
    as a corpus and a namespace, must follow each outline, and is reported once for each it breaks.

    ## Why is this bad?

    An agent that loads the document expects every document of its kind to answer the same questions under the
    same headings; a section the outline does not name holds content no other document of the kind puts there, so
    an agent looking for it in its usual place does not find it.

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

    ## Usage

    Run `lorecraft check` from the repository root.

    ## Tips

    `--strict` fails on a warning.

    ## Options

    `--quiet` prints nothing on success.
    ```

    ## Use instead

    Move the content under a section the outline names:

    ```markdown
    # Check

    ## Usage

    Run `lorecraft check` from the repository root.

    ## Options

    `--strict` fails on a warning.

    `--quiet` prints nothing on success.
    ```

    Attributes:
        spec: The structure specification whose outline does not allow the section.
        section: The heading text of the section the outline does not name, which the occurrence is reported at.
        expected: The section the outline places there instead, which the document writes further down; or `None`
            when the section comes after the outline's end.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 8)
    NAME: ClassVar[RuleName] = RuleName('unexpected-section')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    spec: RootRelativePath
    section: str
    expected: SectionName | None

    def message(self) -> str:
        """Name the section the outline does not name."""
        return f'unexpected section `{self.section}`'

    def labels(self) -> tuple[Label, ...]:
        """Mark the section, with the section the outline places there instead, or that the outline ends before it."""
        if self.expected is None:
            return (Label(Here(self.line), 'the outline ends before it'),)
        return (Label(Here(self.line), f'expected `{self.expected}` here'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification whose outline does not allow the section."""
        return (spec_note(self.spec),)

    @classmethod
    def check(cls, subject: OutlineDivergenceInput) -> tuple[Self, ...]:
        """One occurrence for each outline whose first divergence is a section it does not name.

        Args:
            subject: The first divergence from each governing outline, if any.
        """
        occurrences: list[Self] = []
        for outline_spec in subject.specs:
            divergence = outline_spec.divergence
            match divergence:
                case UnlistedSection():
                    occurrences.append(
                        cls(
                            spec=outline_spec.spec,
                            line=divergence.section.line,
                            section=divergence.section.text,
                            expected=divergence.expected,
                        )
                    )
                case AbsentSection() | MisplacedSection() | None:
                    pass  # the document matches the outline, or diverges from it otherwise
                case _:
                    assert_never(divergence)
        return tuple(occurrences)
