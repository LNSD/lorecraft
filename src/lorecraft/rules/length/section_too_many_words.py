"""`LEN003`: a section of a document holds more prose words than its word cap allows."""

from dataclasses import dataclass
from typing import ClassVar, Final, Self, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.query import ItemQuery
from lorecraft.project.schemas import (
    AnyRunAlignment,
    NamedAlignment,
    OutlineAlignmentSpec,
    UnalignedSection,
    outline_alignment,
)
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Here, Label, Note, Subdiagnostic
from lorecraft.rules.overrun import Overrun, find_overrun
from lorecraft.rules.subject import Facet, QueriedDocumentSkillRule

from .__ruleset__ import GROUP_ID, spec_note


@dataclass(frozen=True, slots=True)
class NamedSectionCap:
    """The cap is the `words` of the outline entry that names the section."""


@dataclass(frozen=True, slots=True)
class AnyRunCap:
    """The cap is the `words` of the `any` run the section falls in, since no outline entry names the section."""


type CapSource = NamedSectionCap | AnyRunCap
"""Where a section's cap comes from: the entry naming it, or the `any` run of unnamed sections it falls in."""


_SPLIT_HELP: Final[Help] = Help(
    'split the section, or move its detail into a document of its own; code blocks and table rows do not count '
    'toward the cap'
)
"""How to bring a section under its cap, and what the cap leaves out of its count."""


def _cap_source_note(cap_source: CapSource, section: str) -> Note:
    """The note saying which entry of the outline the cap is.

    Args:
        cap_source: Whether the cap is the section's own entry's or that of the `any` run it falls in.
        section: The heading text of the section.
    """
    match cap_source:
        case NamedSectionCap():
            return Note(f"the cap is the `{section}` entry's")
        case AnyRunCap():
            return Note("the cap is the `any` run's, which caps each section the outline does not name")
        case _:
            assert_never(cap_source)


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class SectionTooManyWords(QueriedDocumentSkillRule[tuple[OutlineAlignmentSpec, ...]]):
    """A section is longer than its word cap allows.

    ## What it does

    Checks for H2 sections longer than the `words` cap their structure file sets in its `outline`: the
    cap of the entry naming the section, or, for a section the outline does not name, the cap of the `any` run it
    falls in. The cap covers the section's subsections too. Only prose counts: fenced code blocks, table rows and
    headings do not.

    A document that more than one meta spec governs, such as a corpus and a namespace, must keep each section
    within every cap they set, and is reported once for each cap a section exceeds.

    ## Why is this bad?

    A cap keeps a section to what an agent needs from it; every word past it costs the agent context on every load
    and buries the rule it came for.

    ## Example

    `docs/__meta__/guide.spec.json`:

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
        spec: The structure file that sets the exceeded cap.
        section: The heading text of the section, which the occurrence is reported at.
        overrun: The prose words in the section, its subsections included, against the cap they exceed.
        cap_source: Whether the cap is the section's own entry's or that of the `any` run it falls in.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 3)
    NAME: ClassVar[RuleName] = RuleName('section-too-many-words')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GOVERNED_BY: ClassVar[Facet] = Facet.STRUCTURE

    spec: RootRelativePath
    section: str
    overrun: Overrun
    cap_source: CapSource

    def message(self) -> str:
        """Name the section's words found against the cap they exceed."""
        return f'too many words in the section ({self.overrun.count} > {self.overrun.cap})'

    def labels(self) -> tuple[Label, ...]:
        """Say how far past its cap the section runs, at its heading."""
        overrun = self.overrun
        return (
            Label(
                Here(self.line),
                f'`{self.section}` holds {overrun.count} prose words, {overrun.excess} over its cap',
            ),
        )

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the meta spec that sets the cap, say how to shorten the section, and whose cap it is."""
        return (spec_note(self.spec), _SPLIT_HELP, _cap_source_note(self.cap_source, self.section))

    @classmethod
    def query(cls) -> ItemQuery[tuple[OutlineAlignmentSpec, ...]]:
        """The alignment of the document's sections to each outline that governs it."""
        return outline_alignment

    @classmethod
    def judge(cls, facts: tuple[OutlineAlignmentSpec, ...], /) -> tuple[Self, ...]:
        """One occurrence, at its heading, for each section over each cap that applies to it.

        The meta specs are taken in the order they apply, and the sections of each in document order. A section
        takes the cap of the outline entry it is aligned to, which may be none; one aligned to nothing has no cap.

        Args:
            facts: The answer of the rule's query.
        """
        occurrences: list[Self] = []
        for alignment in facts:
            for aligned in alignment.sections:
                cap_source: CapSource  # declared once, so each branch below may assign either variant
                match aligned:
                    case NamedAlignment():
                        cap_source = NamedSectionCap()
                        cap = aligned.entry.words
                    case AnyRunAlignment():
                        cap_source = AnyRunCap()
                        cap = aligned.run.words
                    case UnalignedSection():
                        continue
                    case _:
                        assert_never(aligned)
                section = aligned.section
                if cap is None:
                    continue
                overrun = find_overrun(section.words, cap)
                if overrun is not None:
                    occurrences.append(
                        cls(
                            spec=alignment.spec,
                            line=section.line,
                            section=section.text,
                            overrun=overrun,
                            cap_source=cap_source,
                        )
                    )
        return tuple(occurrences)
