"""`LEN004`: a document's title holds more words than its word cap allows."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import HeadingsInput, HeadingsRule
from lorecraft.rules.location import Elsewhere, Help, Note, Subdiagnostic

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TitleTooManyWords(HeadingsRule):
    """A document's title is longer than its word cap allows.

    ## What it does

    Checks for an H1 title longer than the `words` cap its structure specification sets on `title`. The words are
    those of the title's own text, counted as a section's prose words are: each whitespace-delimited token is one.
    Only the document's first H1 is its title, and a document with no title is not reported here.

    A document that more than one specification governs, such as a corpus and a namespace, must keep its title
    within every cap they set, and is reported once for each cap the title exceeds.

    ## Why is this bad?

    A title is what an agent reads to decide whether the document is the one it needs; a long one says less, not
    more, and costs context in every listing that shows it.

    ## Example

    `docs/__meta__/guide.structure.json`:

    ```json
    {
      "title": { "words": 4 }
    }
    ```

    `docs/guide/setup.md`, with a title of ten words:

    ```markdown
    # How to set up the toolkit on a new machine
    ```

    ## Use instead

    Name what the document is about, and leave the rest to its first paragraph:

    ```markdown
    # Setting up the toolkit
    ```

    Attributes:
        spec: The structure specification that sets the exceeded cap.
        word_count: The words of the title's text.
        cap: The cap it exceeds, in words.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 4)
    NAME: ClassVar[RuleName] = RuleName('title-too-many-words')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    spec: RootRelativePath
    word_count: int
    cap: int

    def message(self) -> str:
        """Name the title's words against the cap they exceed."""
        return f'too many words in the title ({self.word_count} > {self.cap})'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification that sets the cap, and say how many words to cut."""
        return (
            Note('the cap is set here', at=Elsewhere(self.spec)),
            Help(f'cut at least {self.word_count - self.cap} words'),
        )

    @classmethod
    def check(cls, subject: HeadingsInput) -> tuple[Self, ...]:
        """One occurrence, at the title's heading, for each cap on the title that it exceeds.

        Args:
            subject: The document's headings, with what each governing structure specification states over them.
        """
        occurrences: list[Self] = []
        for headings_spec in subject.specs:
            title_cap = headings_spec.title_cap
            if title_cap is None:
                continue
            if title_cap.title_words > title_cap.words.value:
                occurrences.append(
                    cls(
                        spec=headings_spec.spec,
                        line=title_cap.title.line,
                        word_count=title_cap.title_words,
                        cap=title_cap.words.value,
                    )
                )
        return tuple(occurrences)
