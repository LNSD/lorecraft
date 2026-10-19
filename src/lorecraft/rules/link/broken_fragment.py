"""`LINK002`: a link to a heading of the same Markdown file names a heading the file does not have."""

from dataclasses import dataclass
from typing import ClassVar, Self, assert_never
from urllib.parse import unquote

from lorecraft.project.query import ItemQuery, SyntaxPrimitives, item_parse
from lorecraft.project.syntax import (
    AbsoluteDestination,
    Anchor,
    ExternalDestination,
    FragmentDestination,
    Link,
    RelativeDestination,
)
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Note, Subdiagnostic
from lorecraft.rules.subject import QueriedMarkdownRule

from .__ruleset__ import GROUP_ID


@dataclass(frozen=True, slots=True)
class BrokenFragmentFacts:
    """What a rule over fragment-only links reads of a Markdown file.

    Attributes:
        has_headings: Whether the file has any heading.
        links: The fragment-only links naming no heading of the file, in document order.
    """

    has_headings: bool
    links: tuple[Link, ...]


def broken_fragments(primitives: SyntaxPrimitives) -> BrokenFragmentFacts:
    """The fragment-only links of a Markdown file that name none of its headings. Raises nothing.

    A query: it reads the item's links and heading anchors and nothing else.

    Args:
        primitives: The model state of the Markdown file.
    """
    anchors = primitives.query(item_parse).anchors
    broken: list[Link] = []
    for link in primitives.query(item_parse).links:
        destination = link.to_destination()
        match destination:
            case FragmentDestination():
                fragment = destination.fragment
            case ExternalDestination() | AbsoluteDestination() | RelativeDestination():
                continue
            case _:
                assert_never(destination)
        # A bare `#` names no heading at all, so it names no missing one either; nor does a query alone.
        if fragment == '':
            continue
        # `None` is a fragment no heading can have, such as one holding a space, so it is missing whatever the
        # file's headings are.
        anchor = Anchor.from_fragment(fragment)
        if anchor is None or anchor not in anchors:
            broken.append(link)
    # Every heading takes an anchor, so the file has a heading exactly when it has an anchor.
    return BrokenFragmentFacts(has_headings=len(anchors) > 0, links=tuple(broken))


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class BrokenFragment(QueriedMarkdownRule[BrokenFragmentFacts]):
    """A link to a heading of the same Markdown file names a heading the file does not have.

    ## What it does

    Checks for links and images whose destination is a fragment alone, such as `#usage`, naming none of the
    headings of the file that holds them, in every Markdown file the checks read: a document whose corpus states a
    structure file, a skill's `SKILL.md` and each Markdown file inside the skill. No meta spec key
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
    NAME: ClassVar[RuleName] = RuleName('broken-fragment')
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
    def query(cls) -> ItemQuery[BrokenFragmentFacts]:
        """The fragment-only links naming no heading of the file."""
        return broken_fragments

    @classmethod
    def judge(cls, facts: BrokenFragmentFacts, /) -> tuple[Self, ...]:
        """One occurrence for each fragment-only link naming no heading of the file, on its line, in document order.

        Args:
            facts: The links naming no heading, and whether the file has any.
        """
        return tuple(cls(line=link.line, url=link.url, has_headings=facts.has_headings) for link in facts.links)
