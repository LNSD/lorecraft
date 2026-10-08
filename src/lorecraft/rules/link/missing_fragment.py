"""`LINK002`: a link to a heading of the same Markdown file names a heading the file does not have."""

from dataclasses import dataclass
from typing import ClassVar, Self
from urllib.parse import unquote

from lorecraft.project.context import MarkdownContext
from lorecraft.project.syntax import Anchor
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Note, Subdiagnostic
from lorecraft.rules.subject import MarkdownRule

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MissingFragment(MarkdownRule):
    """A link to a heading of the same Markdown file names a heading the file does not have.

    ## What it does

    Checks for links and images whose destination is a fragment alone, such as `#usage`, naming none of the
    headings of the file that holds them, in every Markdown file the checks read: a document whose corpus states a
    structure specification, a skill's `SKILL.md` and each Markdown file inside the skill. No specification key
    states the rule: every such file is held to it.

    A fragment names a heading by its anchor, as GitHub derives it, whatever the case it is written in: `#Usage`
    names `## Usage`. A repeated heading's anchors are numbered, so a second `## Usage` is `#usage-1`. A bare `#`
    names no heading, so it is not reported. A fragment after a path, such as `setup.md#usage`, names a heading of
    another file, which this rule does not check.

    ## Why is this bad?

    A link to a heading that does not exist goes nowhere: an agent that follows it lands at the top of the file, or
    nowhere, and reads the wrong part of it, or none.

    ## Example

    `docs/guide/setup.md`:

    ```markdown
    # Setup

    Every option is listed under [configuration](#configuration).

    ## Options
    ```

    ## Use instead

    Name the heading the file has:

    ```markdown
    # Setup

    Every option is listed under [options](#options).

    ## Options
    ```

    Attributes:
        spec: Always `None`: the package states the rule.
        url: The link's destination as the Markdown parser encodes it, which the message shows percent-decoded.
        has_headings: Whether the file has any heading, which a note says when it has none: no fragment can name one.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 2)
    NAME: ClassVar[RuleName] = RuleName('missing-fragment')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')

    spec: None = None
    url: str
    has_headings: bool

    def message(self) -> str:
        """Name the destination, percent-decoded as the author wrote it."""
        # The parser percent-encodes a destination, so `[x](#Straße)` arrives as `#Stra%C3%9Fe`; the message shows
        # `#Straße`.
        return f'`{unquote(self.url)}` names a heading this file does not have'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say that the file has no headings, when it has none: which heading was meant is the author's to say."""
        if self.has_headings:
            return ()
        return (Note('this file has no headings'),)

    @classmethod
    def check(cls, subject: MarkdownContext) -> tuple[Self, ...]:
        """One occurrence for each fragment-only link naming no heading of the file, on its line, in document order.

        Args:
            subject: The Markdown file whose links are judged against its own headings.
        """
        parsed = subject.parse()
        # Every heading takes an anchor, so the file has a heading exactly when it has an anchor.
        has_headings = len(parsed.anchors) > 0
        occurrences: list[Self] = []
        for link in parsed.links:
            if not link.url.startswith('#'):
                continue
            fragment = link.url.removeprefix('#')
            # A bare `#` names no heading at all, so it names no missing one either.
            if fragment == '':
                continue
            # `None` is a fragment no heading can have, such as one holding a space, so it is missing whatever the
            # file's headings are.
            anchor = Anchor.from_fragment(fragment)
            if anchor is None or anchor not in parsed.anchors:
                occurrences.append(cls(line=link.line, url=link.url, has_headings=has_headings))
        return tuple(occurrences)
