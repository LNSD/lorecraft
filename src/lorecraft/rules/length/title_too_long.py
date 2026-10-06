"""`LEN005`: a document's title holds more characters than its character cap allows."""

from dataclasses import dataclass
from typing import ClassVar, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.inputs import HeadingsInput, HeadingsRule
from lorecraft.rules.location import Elsewhere, Help, Note, Subdiagnostic

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TitleTooLong(HeadingsRule):
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

    spec: RootRelativePath
    char_count: int
    cap: int

    def message(self) -> str:
        """Name the title's characters against the cap they exceed."""
        return f'too many characters in the title ({self.char_count} > {self.cap})'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification that sets the cap, and say how many characters to cut."""
        return (
            Note('the cap is set here', at=Elsewhere(self.spec)),
            Help(f'cut at least {self.char_count - self.cap} characters'),
        )

    @classmethod
    def check(cls, subject: HeadingsInput) -> tuple[Self, ...]:
        """One occurrence, at the title's heading, for each cap on the title's characters that it exceeds.

        Args:
            subject: The document's headings, with what each governing structure specification states over them.
        """
        occurrences: list[Self] = []
        for headings_spec in subject.specs:
            title_char_cap = headings_spec.title_char_cap
            if title_char_cap is None:
                continue
            if title_char_cap.title_chars > title_char_cap.chars.value:
                occurrences.append(
                    cls(
                        spec=headings_spec.spec,
                        line=title_char_cap.title.line,
                        char_count=title_char_cap.title_chars,
                        cap=title_char_cap.chars.value,
                    )
                )
        return tuple(occurrences)
