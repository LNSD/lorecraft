"""`LEN003`: a section of a document holds more prose words than its word cap allows."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import HeadingsInput, HeadingsRule
from lorecraft.rules.location import Elsewhere, Note, Subdiagnostic

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TooManyWords(HeadingsRule):
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
        word_count: The prose words in the section, its subsections included.
        cap: The cap it exceeds, in words.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 3)
    NAME: ClassVar[RuleName] = RuleName('too-many-words')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    spec: RootRelativePath
    word_count: int
    cap: int

    def message(self) -> str:
        """Name the words found against the cap they exceed."""
        return f'too many words ({self.word_count} > {self.cap})'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification that sets the cap."""
        return (Note('the cap is set here', at=Elsewhere(self.spec)),)

    @classmethod
    def check(cls, subject: HeadingsInput) -> tuple[Self, ...]:
        """One occurrence, at its heading, for each section over each cap that applies to it.

        Args:
            subject: The document's headings, with what each governing structure specification states over them.
        """
        occurrences: list[Self] = []
        for headings_spec in subject.specs:
            for section_cap in headings_spec.section_caps:
                section = section_cap.section
                if section.words > section_cap.words.value:
                    occurrences.append(
                        cls(
                            spec=headings_spec.spec,
                            line=section.line,
                            word_count=section.words,
                            cap=section_cap.words.value,
                        )
                    )
        return tuple(occurrences)
