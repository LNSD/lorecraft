"""`OUT001`: a document carries fewer H1 titles than its structure specification requires."""

from dataclasses import dataclass
from typing import ClassVar, Final, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import HeadingsInput, HeadingsRule
from lorecraft.rules.location import Subdiagnostic

from .__ruleset__ import GROUP_ID, spec_note

_FIRST_LINE: Final[LineNumber] = LineNumber.from_int(1)
"""Where an occurrence is reported: the document's first line, since a missing title has no heading of its own."""


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MissingTitle(HeadingsRule):
    """A document carries fewer H1 titles than its structure specification requires.

    ## What it does

    Checks for documents with fewer `#` H1 headings than the `count` their structure specification sets under its
    `title` key. Only a heading at the top level of the document counts: one inside a list or a blockquote does not.

    A document that more than one specification governs, such as a corpus and a namespace, must carry the titles
    each of them requires, and is reported once for each specification it falls short of.

    ## Why is this bad?

    An agent reads the title to learn what the document is about before it reads the rest; without one it has to
    guess from the first section, and a link or a listing that shows the title shows nothing.

    ## Example

    `docs/__meta__/guide.structure.json`:

    ```json
    {
      "title": {
        "count": 1,
        "first": true
      }
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
        spec: The structure specification whose title rule the document falls short of.
        found: The H1 titles the document carries.
        count: The H1 titles the specification requires.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 1)
    NAME: ClassVar[RuleName] = RuleName('missing-title')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    spec: RootRelativePath
    found: int
    count: int

    def message(self) -> str:
        """Name the titles found against the titles required."""
        return f'missing H1 title ({self.found} < {self.count})'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification that requires the titles."""
        return (spec_note(self.spec),)

    @classmethod
    def check(cls, subject: HeadingsInput) -> tuple[Self, ...]:
        """One occurrence, on line 1, for each specification whose title count the document falls short of.

        Args:
            subject: The document's headings, with what each governing structure specification states over them.
        """
        found = 0
        for heading in subject.headings:
            if heading.level == 1:
                found += 1
        occurrences: list[Self] = []
        for headings_spec in subject.specs:
            title = headings_spec.title
            if title is not None and found < title.count.value:
                occurrences.append(cls(spec=headings_spec.spec, line=_FIRST_LINE, found=found, count=title.count.value))
        return tuple(occurrences)
