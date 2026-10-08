"""`OUT001`: a document a structure specification governs carries no H1 title."""

from dataclasses import dataclass
from typing import ClassVar, Final, Self

from lorecraft.project.context import DocumentContext
from lorecraft.project.syntax import LineNumber, find_title
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Help, Subdiagnostic
from lorecraft.rules.subject import DocumentRule, Facet

from .__ruleset__ import GROUP_ID

_FIRST_LINE: Final[LineNumber] = LineNumber.from_int(1)
"""Where an occurrence is reported: the document's first line, since a missing title has no heading of its own."""


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MissingTitle(DocumentRule):
    """A document a structure specification governs carries no H1 title.

    ## What it does

    Checks for documents with no `#` H1 heading. Every document a structure specification governs is held to it,
    with no key to state it: the specification need not mention the title at all. Only a heading at the top level
    of the document counts: one inside a list or a blockquote does not.

    A document that more than one specification governs, such as a corpus and a namespace, is reported once.

    ## Why is this bad?

    An agent reads the title to learn what the document is about before it reads the rest; without one it has to
    guess from the first section, and a link or a listing that shows the title shows nothing.

    ## Example

    `docs/__meta__/guide.structure.json`:

    ```json
    {
      "empty_sections": "forbidden"
    }
    ```

    `docs/guide/setup.md`:

    ```markdown
    ## Install

    Install the toolkit, then run it once over the repository.
    ```

    ## Use instead

    Open the document with its title:

    ```markdown
    # Setup

    ## Install

    Install the toolkit, then run it once over the repository.
    ```

    Attributes:
        spec: Always `None`: the package states the rule.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 1)
    NAME: ClassVar[RuleName] = RuleName('missing-title')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GOVERNED_BY: ClassVar[Facet] = Facet.STRUCTURE

    spec: None = None

    def message(self) -> str:
        """State that the title is missing."""
        return 'missing H1 title'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say how to write the title."""
        return (Help('open the document with an H1 title, `# <title>`'),)

    @classmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """One occurrence, on line 1, when the document has no H1 title.

        Args:
            subject: The document, governed by a structure specification.
        """
        if find_title(subject.parse().headings) is not None:
            return ()
        return (cls(line=_FIRST_LINE),)
