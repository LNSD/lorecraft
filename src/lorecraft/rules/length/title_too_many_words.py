"""`LEN004`: a document's title holds more words than its word cap allows."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import DocumentContext
from lorecraft.project.syntax import count_words, find_title
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Here, Label, Subdiagnostic
from lorecraft.rules.subject import DocumentRule, Facet

from .__ruleset__ import GROUP_ID, TITLE_HELP, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TitleTooManyWords(DocumentRule):
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
    GOVERNED_BY: ClassVar[Facet] = Facet.STRUCTURE

    spec: RootRelativePath
    word_count: int
    cap: int

    def message(self) -> str:
        """Name the title's words against the cap they exceed."""
        return f'too many words in the title ({self.word_count} > {self.cap})'

    def labels(self) -> tuple[Label, ...]:
        """Say how many words the title runs past its cap, at the title."""
        return (Label(Here(self.line), f'words over the cap: {self.word_count - self.cap}'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification that sets the cap, then say what a title holds."""
        return (spec_note(self.spec), TITLE_HELP)

    @classmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """One occurrence, at the title's heading, for each cap on the title that it exceeds.

        The caps are taken in the order their specifications apply; a document with no title is held to none.

        Args:
            subject: The document, governed by a structure specification.
        """
        title = find_title(subject.parse().headings)
        if title is None:
            return ()
        word_count = count_words(title.text)
        occurrences: list[Self] = []
        for structure_spec in subject.specifications().structure_specs():
            title_checks = structure_spec.title
            if title_checks is None or title_checks.words is None:
                continue
            cap = title_checks.words.value
            if word_count > cap:
                occurrences.append(cls(spec=structure_spec.path, line=title.line, word_count=word_count, cap=cap))
        return tuple(occurrences)
