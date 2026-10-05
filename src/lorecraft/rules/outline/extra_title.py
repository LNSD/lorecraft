"""`OUT002`: a document a structure specification governs carries more than one H1 title."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import Heading, LineNumber
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import HeadingsInput, HeadingsRule
from lorecraft.rules.location import Here, Label, Subdiagnostic

from .__ruleset__ import GROUP_ID, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class ExtraTitle(HeadingsRule):
    """A document a structure specification governs carries more than one H1 title.

    ## What it does

    Checks for documents with more than one `#` H1 heading, and reports each H1 after the first at its own heading,
    pointing back at the first: the first is the document's title, and every one after it is extra. Every document
    a structure specification governs is held to it, with no key to state it: the specification need not mention
    the title at all. Only a heading at the top level of the document counts: one inside a list or a blockquote does
    not.

    A document that more than one specification governs, such as a corpus and a namespace, has each extra title
    reported once, under its corpus's structure specification.

    ## Why is this bad?

    An agent reads the title to learn what the document is about; a second title reads as a second document, so the
    agent cannot tell which one the document is, nor that the sections under the second belong to the first.

    ## Example

    `docs/__meta__/guide.structure.json`:

    ```json
    {
      "empty_sections": "forbidden"
    }
    ```

    `docs/guide/setup.md`:

    ```markdown
    # Setup

    ## Install

    Install the toolkit, then run it once over the repository.

    # Usage

    Run it over the repository's documents.
    ```

    ## Use instead

    Keep one title, and make the rest sections:

    ```markdown
    # Setup

    ## Install

    Install the toolkit, then run it once over the repository.

    ## Usage

    Run it over the repository's documents.
    ```

    Attributes:
        spec: The corpus's structure specification, which governs the document.
        first_line: The line of the document's first H1 title, its own.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 2)
    NAME: ClassVar[RuleName] = RuleName('extra-title')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    spec: RootRelativePath
    first_line: LineNumber

    def message(self) -> str:
        """Name the line of the document's own title."""
        return f'extra H1 title, the document is titled on line {self.first_line}'

    def labels(self) -> tuple[Label, ...]:
        """Point at the document's own title."""
        return (Label(Here(self.first_line), 'title written here'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the corpus's structure specification."""
        return (spec_note(self.spec),)

    @classmethod
    def check(cls, subject: HeadingsInput) -> tuple[Self, ...]:
        """One occurrence per H1 title after the first, at its heading, under the corpus's structure specification.

        Args:
            subject: The document's headings, with the corpus's structure specification that governs them.
        """
        titles: list[Heading] = []
        for heading in subject.headings:
            if heading.level == 1:
                titles.append(heading)
        if not titles:
            return ()
        first = titles[0]
        occurrences: list[Self] = []
        for extra in titles[1:]:
            occurrences.append(cls(spec=subject.corpus.spec, line=extra.line, first_line=first.line))
        return tuple(occurrences)
