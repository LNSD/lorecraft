"""`LINK004`: a relative link climbs above the bound of its link base."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Self, assert_never
from urllib.parse import unquote

from lorecraft.project.item import ItemType
from lorecraft.project.link_target import DocumentDirectory, EscapingTarget, LinkBase, LinkTarget, SkillRoot
from lorecraft.project.query import ItemQuery, item_parse
from lorecraft.project.syntax import (
    AbsoluteDestination,
    ExternalDestination,
    FragmentDestination,
    Link,
    RelativeDestination,
)
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Subdiagnostic
from lorecraft.rules.subject import Always, Gate, QueriedItemRule

from .__ruleset__ import GROUP_ID, SKILL_NOTE, SyntaxLinkResolutionPrimitives


def escaping_links(primitives: SyntaxLinkResolutionPrimitives) -> tuple[tuple[Link, LinkBase], ...]:
    """The relative links whose path climbs above the bound of their link base, in file order.

    A query: it reads the item's links and their targets and nothing else.

    Args:
        primitives: The model state of a Markdown item's file and link base.
    """
    base = primitives.link_base()
    if base is None:
        return ()
    targets = primitives.link_targets()
    escaping: list[tuple[Link, LinkBase]] = []
    for link in primitives.query(item_parse).links:
        # The link target records whether the path climbs past this item's link-base bound.
        destination = link.to_destination()
        match destination:
            case RelativeDestination():
                entry = targets.get(destination.path)
            # A URL with a scheme, an absolute or a fragment-only link spells no relative path, so it never escapes.
            case ExternalDestination() | AbsoluteDestination() | FragmentDestination():
                continue
            case _:
                assert_never(destination)
        match entry:
            case EscapingTarget():
                escaping.append((link, base))
            # A target inside the link base's bound, or none.
            case LinkTarget() | None:
                continue
            case _:
                assert_never(entry)
    return tuple(escaping)


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class EscapingLink(QueriedItemRule[tuple[tuple[Link, LinkBase], ...]]):
    """A relative link climbs above the bound of its link base.

    ## What it does

    Checks relative links and images in documents, meta specs and skills. Documents and meta specs read links from
    their own directory and may climb within the repository, but not above its root. Skills and resources read links
    from the skill root and may not climb above that root.

    A path that climbs and comes back down inside its bound stays inside. A URL with a scheme, an absolute link, or
    a fragment-only link spells no relative path, so none is reported.

    ## Why is this bad?

    A link above its base's bound names a path the project cannot reliably provide. Skills may be installed
    independently; documents and meta specs cannot name paths outside the repository snapshot.

    ## Example

    `docs/guide/setup.md`:

    ```markdown
    # Checklist

    Start from [the repository file](../../../outside.md).
    ```

    ## Use instead

    Keep the link within its base's bound:

    ```markdown
    # Checklist

    Start from [the repository file](../code/guide.md).
    ```

    Attributes:
        spec: Always `None`: the package states the rule.
        url: The link's destination as the Markdown parser encodes it, which the message shows percent-decoded.
        base: The link base defining the bound the destination climbs above.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 4)
    NAME: ClassVar[RuleName] = RuleName('escaping-link')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    APPLIES_TO: ClassVar[Mapping[ItemType, Gate]] = MappingProxyType({item_type: Always() for item_type in ItemType})

    spec: None = None
    url: str
    base: LinkBase

    def message(self) -> str:
        """Name the destination and the bound it leaves, percent-decoded as the author wrote it."""
        # The parser percent-encodes a destination, so `[x](<../a b>)` arrives as `../a%20b`; the message shows
        # `../a b`.
        match self.base:
            case SkillRoot():
                bound = 'skill root'
            case DocumentDirectory():
                bound = 'repository root'
            case _:
                assert_never(self.base)
        return f'`{unquote(self.url)}` leaves the {bound}'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the governing link base, then say how to name the file."""
        match self.base:
            case SkillRoot():
                return (SKILL_NOTE, Help('link a file inside the skill, relative to the skill root'))
            case DocumentDirectory():
                return (Help('link a file inside the repository'),)
            case _:
                assert_never(self.base)

    @classmethod
    def query(cls) -> ItemQuery[tuple[tuple[Link, LinkBase], ...]]:
        """The relative links whose path climbs above the bound of their link base."""
        return escaping_links

    @classmethod
    def judge(cls, facts: tuple[tuple[Link, LinkBase], ...], /) -> tuple[Self, ...]:
        """One occurrence for each relative link whose path climbs above its base's bound, on its line, in file order.

        Args:
            facts: The escaping links and their link bases.
        """
        return tuple(cls(line=link.line, url=link.url, base=base) for link, base in facts)
