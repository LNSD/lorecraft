"""`OUT006`: a document lacks a section its outline requires."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import DocumentContext
from lorecraft.project.schemas import AbsentSection, DocumentEnd, MisplacedSection, SectionName, UnlistedSection
from lorecraft.project.syntax import Heading
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Here, Label, Subdiagnostic
from lorecraft.rules.subject import DocumentRule, Facet

from .__ruleset__ import GROUP_ID, example_note, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MissingSection(DocumentRule):
    """A document lacks a section its outline requires.

    ## What it does

    Checks for documents that leave out a section their structure specification lists under its `outline` key
    without `"optional": true`. The section is expected before the section written where it belongs, or at the
    end of the document when no section follows. The entry's `description` is shown as help, and its first
    `examples` sample as a note, written under the section's heading.

    Only the first place a document stops following its outline is reported, since every section after it is
    compared with an entry it was never meant to match; a section that is only written further down is out of
    order, not missing. A document that more than one specification governs, such as a corpus and a namespace,
    must follow each outline, and is reported once for each it breaks.

    ## Why is this bad?

    An agent that loads the document expects every document of its kind to answer the same questions in the same
    sections; a section left out is a question the agent cannot tell is unanswered from one it skipped.

    ## Example

    `docs/__meta__/guide.structure.json`:

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
        spec: The structure specification whose outline requires the section.
        section: The heading text of the section the document lacks.
        before: The heading of the section it should come before, which the occurrence is reported at; or the end
            of the document, when it belongs there, and the occurrence is reported at the document's last line.
        description: What the section holds, as the outline entry states it, or `None` when it states none.
        example: The first sample of the section's body the outline entry gives, or `None` when it gives none.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 6)
    NAME: ClassVar[RuleName] = RuleName('missing-section')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GOVERNED_BY: ClassVar[Facet] = Facet.OUTLINE

    spec: RootRelativePath
    section: SectionName
    before: Heading | DocumentEnd
    description: str | None
    example: str | None

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
            case Heading():
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
        """Point at the specification, then give the entry's description and its first example, when it states them.

        Any further examples are for a reader of the specification, not repeated on every occurrence.
        """
        parts: list[Subdiagnostic] = [spec_note(self.spec)]
        if self.description is not None:
            parts.append(Help(self.description))
        if self.example is not None:
            parts.append(example_note(self.section.value, self.example))
        return tuple(parts)

    @classmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """One occurrence for each outline whose first divergence is a required section the document lacks.

        An occurrence has a line of the document as its primary location, so one expected at the end of the
        document is reported at its last line, the nearest line to where the section would be written.

        Args:
            subject: The document, governed by at least one outline.
        """
        occurrences: list[Self] = []
        for outline_spec in subject.outline_divergences():
            divergence = outline_spec.divergence
            match divergence:
                case AbsentSection():
                    occurrences.append(cls._from_absent(outline_spec.spec, divergence))
                case MisplacedSection() | UnlistedSection() | None:
                    pass  # the document matches the outline, or diverges from it otherwise
                case _:
                    assert_never(divergence)
        return tuple(occurrences)

    @classmethod
    def _from_absent(cls, spec: RootRelativePath, absent: AbsentSection) -> Self:
        """The occurrence of one absent section, at the section it should precede or at the document's last line.

        Args:
            spec: The structure specification whose outline requires the section.
            absent: The required section the document holds nowhere.
        """
        before = absent.before
        match before:
            case Heading():
                line = before.line
            case DocumentEnd():
                line = before.last_line
            case _:
                assert_never(before)
        return cls(
            spec=spec,
            line=line,
            section=absent.name,
            before=before,
            description=absent.description,
            example=absent.example,
        )
