"""`LEN005`: a document's title holds more characters than its character cap allows."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import DocumentContext
from lorecraft.project.syntax import find_title
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Here, Label, Note, Subdiagnostic
from lorecraft.rules.subject import DocumentRule, Facet

from .__ruleset__ import GROUP_ID, TITLE_HELP, spec_note


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TitleTooLong(DocumentRule):
    """A document's title is longer than its character cap allows.

    ## What it does

    Checks for an H1 title longer than the `chars` cap its structure specification sets on `title`. The characters
    are those of the title's own text, without its `#` marker or inline markup, counted as Unicode code points: a
    space is one, and so is each code point of an emoji built of several. Only the document's first H1 is its title,
    and a document with no title is not reported here.

    A document that more than one specification governs, such as a corpus and a namespace, must keep its title
    within every cap they set, and is reported once for each cap the title exceeds.

    ## Why is this bad?

    A title is what an agent or a reader scans when documents are listed by title; a wide one overflows the
    listing, and a word cap alone does not bound it when a few of its words are long, such as a command or a path.

    ## Example

    `docs/__meta__/guide.structure.json`:

    ```json
    {
      "title": { "chars": 24 }
    }
    ```

    `docs/guide/setup.md`, with a title of 36 characters, its backticks not counted:

    ```markdown
    # Setting up `lorecraft check structure`
    ```

    ## Use instead

    Name what the document is about, and leave the rest to its first paragraph:

    ```markdown
    # Setting up the checks
    ```

    Attributes:
        spec: The structure specification that sets the exceeded cap.
        char_count: The characters of the title's text.
        cap: The cap it exceeds, in characters.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 5)
    NAME: ClassVar[RuleName] = RuleName('title-too-long')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GOVERNED_BY: ClassVar[Facet] = Facet.STRUCTURE

    spec: RootRelativePath
    char_count: int
    cap: int

    def message(self) -> str:
        """Name the title's characters against the cap they exceed."""
        return f'too many characters in the title ({self.char_count} > {self.cap})'

    def labels(self) -> tuple[Label, ...]:
        """Say how many characters the title runs past its cap, at the title."""
        return (Label(Here(self.line), f'characters over the cap: {self.char_count - self.cap}'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification that sets the cap, say what a title holds, and how its characters are counted."""
        return (
            spec_note(self.spec),
            TITLE_HELP,
            Note(
                "characters are counted as the code points of the title's text, without its # marker or inline markup"
            ),
        )

    @classmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """One occurrence, at the title's heading, for each cap on the title's characters that it exceeds.

        The caps are taken in the order their specifications apply; a document with no title is held to none.

        Args:
            subject: The document, governed by a structure specification.
        """
        title = find_title(subject.parse().headings)
        if title is None:
            return ()
        # The parse holds the title's text with its inline markup stripped, and `len` counts its Unicode code
        # points: neither its bytes nor the letters a reader sees, so an emoji built of several counts each of them.
        char_count = len(title.text)
        occurrences: list[Self] = []
        for structure_spec in subject.specifications().structure_specs():
            title_checks = structure_spec.title
            if title_checks is None or title_checks.chars is None:
                continue
            cap = title_checks.chars.value
            if char_count > cap:
                occurrences.append(cls(spec=structure_spec.path, line=title.line, char_count=char_count, cap=cap))
        return tuple(occurrences)
