"""`LEN003`: a section of a document holds more prose words than its word cap allows."""

from dataclasses import dataclass
from typing import ClassVar, Final, Self, assert_never

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import DocumentContext
from lorecraft.project.schemas import AnySections, OutlineEntry, SectionEntry
from lorecraft.project.syntax import SECTION_LEVEL
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Here, Label, Note, Subdiagnostic
from lorecraft.rules.subject import DocumentRule, Facet

from .__ruleset__ import GROUP_ID, spec_note


@dataclass(frozen=True, slots=True)
class NamedSectionCap:
    """The cap is the `words` of the outline entry that names the section."""


@dataclass(frozen=True, slots=True)
class AnyRunCap:
    """The cap is the `words` of the `any` run the section falls in, since no outline entry names the section."""


type CapSource = NamedSectionCap | AnyRunCap
"""Where a section's cap comes from: the entry naming it, or the run of unnamed sections it falls in."""


_SPLIT_HELP: Final[Help] = Help(
    'split the section, or move its detail into a document of its own; code blocks and table rows do not count '
    'toward the cap'
)
"""How to bring a section under its cap, and what the cap leaves out of its count."""


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TooManyWords(DocumentRule):
    """A section is longer than its word cap allows.

    ## What it does

    Checks for H2 sections longer than the `words` cap their structure specification sets in its `outline`: the
    cap of the entry naming the section, or, for a section the outline does not name, the cap of the `any` run it
    falls in. The cap covers the section's subsections too. Only prose counts: fenced code blocks, table rows and
    headings do not.

    A document that more than one specification governs, such as a corpus and a namespace, must keep each section
    within every cap they set, and is reported once for each cap a section exceeds.

    ## Why is this bad?

    A cap keeps a section to what an agent needs from it; every word past it costs the agent context on every load
    and buries the rule it came for.

    ## Example

    `docs/__meta__/guide.structure.json`:

    ```json
    {
      "outline": [
        { "section": "Configuration", "words": 150 }
      ]
    }
    ```

    `docs/guide/setup.md`, with a `Configuration` section of 420 words:

    ```markdown
    # Setup

    ## Configuration

    Every option the configuration file accepts, with its default and the reasons to change it:

    <!-- ... 400 more words, one paragraph per option -->
    ```

    ## Use instead

    Keep what an agent needs on every load, and move the rest into a document of its own:

    ```markdown
    # Setup

    ## Configuration

    Every option the configuration file accepts is described in [configuration](configuration.md).
    ```

    Attributes:
        spec: The structure specification that sets the exceeded cap.
        section: The heading text of the section, which the occurrence is reported at.
        word_count: The prose words in the section, its subsections included.
        cap: The cap it exceeds, in words.
        cap_source: Whether the cap is the section's own entry's or that of the `any` run it falls in.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 3)
    NAME: ClassVar[RuleName] = RuleName('too-many-words')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    # STRUCTURE, not OUTLINE, though only the outline is read: it judges the same documents as the rules over the
    # headings (owner decision).
    GOVERNED_BY: ClassVar[Facet] = Facet.STRUCTURE

    spec: RootRelativePath
    section: str
    word_count: int
    cap: int
    cap_source: CapSource

    def message(self) -> str:
        """Name the section's words found against the cap they exceed."""
        return f'too many words in the section ({self.word_count} > {self.cap})'

    def labels(self) -> tuple[Label, ...]:
        """Say how far past its cap the section runs, at its heading."""
        over = self.word_count - self.cap
        return (Label(Here(self.line), f'`{self.section}` holds {self.word_count} prose words, {over} over its cap'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification that sets the cap, say how to shorten the section, and whose cap it is."""
        return (spec_note(self.spec), _SPLIT_HELP, self._cap_source_note())

    def _cap_source_note(self) -> Note:
        """The note saying which entry of the outline the cap is."""
        match self.cap_source:
            case NamedSectionCap():
                return Note(f"the cap is the `{self.section}` entry's")
            case AnyRunCap():
                return Note("the cap is the `any` run's, which caps each section the outline does not name")
            case _:
                assert_never(self.cap_source)

    @classmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """One occurrence, at its heading, for each section over each cap that applies to it.

        The specifications are taken in the order they apply, and the sections of each in document order.

        Args:
            subject: The document, governed by a structure specification.
        """
        sections = [heading for heading in subject.parse().headings if heading.level == SECTION_LEVEL]
        occurrences: list[Self] = []
        for structure_spec in subject.specifications().structure_specs():
            outline = structure_spec.outline
            last_named_at = -1  # the outline index of the last named section passed; -1 before any
            for section in sections:
                cap_source: CapSource  # declared once, so each branch below may assign either variant
                # A section the outline names takes the cap of the entry naming it, which may be none. Any other
                # section takes the cap of the `any` run it falls in: the first `any` entry after the entry naming
                # the last named section before it. In a document that follows the outline, that is the run which
                # matches it.
                entry_at = _find_entry_index(outline, section.text)
                if entry_at is None:
                    cap = _find_run_cap(outline, last_named_at)
                    cap_source = AnyRunCap()
                else:
                    last_named_at = entry_at
                    cap = outline[entry_at].words
                    cap_source = NamedSectionCap()
                if cap is not None and section.words > cap.value:
                    occurrences.append(
                        cls(
                            spec=structure_spec.path,
                            line=section.line,
                            section=section.text,
                            word_count=section.words,
                            cap=cap.value,
                            cap_source=cap_source,
                        )
                    )
        return tuple(occurrences)


def _find_entry_index(outline: tuple[OutlineEntry, ...], name: str) -> int | None:
    """Where in the outline the section entry naming `name` sits, or `None` when no entry names it. Raises nothing.

    Args:
        outline: The entries to search, in outline order.
        name: Heading text of the section to find.
    """
    for index, entry in enumerate(outline):
        match entry:
            case SectionEntry():
                if entry.name.value == name:
                    return index
            case AnySections():
                pass  # a run names no section
            case _:
                assert_never(entry)
    return None


def _find_run_cap(outline: tuple[OutlineEntry, ...], after: int) -> NonZeroUnsignedInt | None:
    """The cap of the first `any` entry past outline index `after`, or `None` when there is none. Raises nothing.

    Args:
        outline: The entries to search, in outline order.
        after: Outline index of the last named section passed, exclusive; -1 searches from the start.
    """
    for entry in outline[after + 1 :]:
        match entry:
            case AnySections():
                return entry.words
            case SectionEntry():
                pass  # a section entry caps only its own section
            case _:
                assert_never(entry)
    return None
