"""`OUT006`: a document lacks a section its outline requires."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.item import ItemKind
from lorecraft.project.query import ItemQuery
from lorecraft.project.schemas import (
    AbsentSection,
    DocumentEnd,
    MisplacedSection,
    OutlineDivergenceSpec,
    SectionName,
    UnlistedSection,
)
from lorecraft.project.syntax import LineNumber, SectionHeading
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
from lorecraft.rules.subject import ByMetaSpec, Gate, MetaSpecPart, QueriedItemRule

from .__ruleset__ import GROUP_ID, example_note, outline_divergences, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MissingSection(QueriedItemRule[tuple[OutlineDivergenceSpec, ...]]):
    """A document lacks a section its outline requires.

    ## What it does

    Checks for documents that leave out a section their structure file lists under its `outline` key
    without `"optional": true`. The section is expected before the section written where it belongs, or at the
    end of the document when no section follows. The entry's `description` is shown as help, and its first
    `examples` sample as a note, written under the section's heading.

    Only the first place a document stops following its outline is reported, since every section after it is
    compared with an entry it was never meant to match; a section that is only written further down is out of
    order, not missing. A document that more than one meta spec governs, such as a corpus and a namespace,
    must follow each outline, and is reported once for each it breaks.

    ## Why is this bad?

    An agent that loads the document expects every document of its kind to answer the same questions in the same
    sections; a section left out is a question the agent cannot tell is unanswered from one it skipped.

    ## Example

    `docs/__meta__/guide.spec.json`:

    ```json
    {
      "outline": [
        {"section": "Usage", "description": "How to invoke the command."},
        {"section": "Options"}
      ]
    }
    ```

    `docs/guide/check.md`:

    ```markdown
    # Check

    ## Options

    `--strict` fails on a warning.
    ```

    ## Use instead

    Write the section where the outline places it:

    ```markdown
    # Check

    ## Usage

    Run `lorecraft check` from the repository root.

    ## Options

    `--strict` fails on a warning.
    ```

    Attributes:
        spec: The structure file whose outline requires the section.
        section: The name the outline entry gives the section the document lacks.
        before: The heading of the section it should come before, which the occurrence is reported at; or the end
            of the document, when it belongs there, and the occurrence is reported at the document's last line.
        description: What the section holds, as the outline entry states it, or `None` when it states none.
        example: The first sample of the section's body the outline entry gives, or `None` when it gives none.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 6)
    NAME: ClassVar[RuleName] = RuleName('missing-section')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: ByMetaSpec(MetaSpecPart.OUTLINE),
            ItemKind.SKILL_ENTRYPOINT: ByMetaSpec(MetaSpecPart.OUTLINE),
        }
    )

    spec: RootRelativePath
    # Reported at the section it should precede, or else at the document's last line, so it is derived from `before`
    # and no caller can state a line that disagrees with it.
    line: LineNumber = field(init=False)
    section: SectionName
    before: SectionHeading | DocumentEnd
    description: str | None
    example: str | None

    def __post_init__(self) -> None:
        """Derive the reported line from where the section belongs."""
        before = self.before
        match before:
            case SectionHeading():
                line = before.line
            case DocumentEnd():
                line = before.last_line
            case _:
                assert_never(before)
        # The dataclass is frozen, so the field a rule derives is set the one way a frozen dataclass allows.
        object.__setattr__(self, 'line', line)

    def message(self) -> str:
        """Name the section the document lacks."""
        return f'missing required section `{self.section}`'

    def labels(self) -> tuple[Label, ...]:
        """Mark where the section is expected: before the section reported at, or after the document's last section.

        A section expected at the end is reported at the document's last line, which may be a blank line or the end
        of a code block, so the last section is labelled too, when the document has one.
        """
        before = self.before
        match before:
            case SectionHeading():
                return (Label(Here(self.line), f'expected `{self.section}` before `{before.text}`'),)
            case DocumentEnd():
                after = before.after
                if after is None:
                    return (Label(Here(self.line), f'expected `{self.section}` before the end of the document'),)
                after_label = Label(Here(after.line), f'expected `{self.section}` after `{after.text}`')
                if after.line == self.line:
                    # The last section's heading is the document's last line: one label says it all.
                    return (after_label,)
                return (
                    Label(Here(self.line), f'expected `{self.section}` before the end of the document'),
                    after_label,
                )
            case _:
                assert_never(before)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the meta spec, then give the entry's description and its first example, when it states them.

        Any further examples are for a reader of the meta spec, not repeated on every occurrence.
        """
        parts: list[Subdiagnostic] = [spec_note(self.spec)]
        if self.description is not None:
            parts.append(Help(self.description))
        if self.example is not None:
            parts.append(example_note(self.section, self.example))
        return tuple(parts)

    @classmethod
    def query(cls) -> ItemQuery[tuple[OutlineDivergenceSpec, ...]]:
        """The outline divergences of the document, one for each outline that governs it."""
        return outline_divergences

    @classmethod
    def judge(cls, facts: tuple[OutlineDivergenceSpec, ...], /) -> tuple[Self, ...]:
        """One occurrence for each outline whose first divergence is a required section the document lacks.

        An occurrence has a line of the document as its primary location, so one expected at the end of the
        document is reported at its last line, the nearest line to where the section would be written.

        Args:
            facts: The answer of the rule's query.
        """
        occurrences: list[Self] = []
        for outline_spec in facts:
            divergence = outline_spec.divergence
            match divergence:
                case AbsentSection():
                    occurrences.append(
                        cls(
                            spec=outline_spec.spec,
                            section=divergence.name,
                            before=divergence.before,
                            description=divergence.description,
                            example=divergence.example,
                        )
                    )
                case MisplacedSection() | UnlistedSection() | None:
                    pass  # the document matches the outline, or diverges from it otherwise
                case _:
                    assert_never(divergence)
        return tuple(occurrences)
