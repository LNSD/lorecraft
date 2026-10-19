"""`LINK001`: a link in a Markdown file starts at a filesystem root."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Self, assert_never
from urllib.parse import unquote

from lorecraft.project.item import ItemKind
from lorecraft.project.query import ItemQuery, SyntaxPrimitives, item_parse
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
from lorecraft.rules.subject import ByMetaSpec, ByPackage, Gate, MetaSpecPart, QueriedItemRule

from .__ruleset__ import GROUP_ID


def absolute_links(primitives: SyntaxPrimitives) -> tuple[Link, ...]:
    """The links and images of a Markdown file whose destination starts with `/`, in document order.

    A query: it reads the item's links and nothing else.

    Args:
        primitives: The model state of the Markdown file.
    """
    absolute: list[Link] = []
    for link in primitives.query(item_parse).links:
        destination = link.to_destination()
        match destination:
            case AbsoluteDestination():
                absolute.append(link)
            case ExternalDestination() | FragmentDestination() | RelativeDestination():
                pass
            case _:
                assert_never(destination)
    return tuple(absolute)


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class AbsoluteLink(QueriedItemRule[tuple[Link, ...]]):
    """A link in a Markdown file starts at a filesystem root.

    ## What it does

    Checks for links and images whose destination starts with `/`, as written or once percent-decoded, so
    `%2Fetc/x.md` is reported too, in every Markdown file the checks read: a
    document whose corpus states a structure file, a skill's `SKILL.md` and each Markdown file inside the
    skill. No meta spec key states the rule: every such file is held to it.

    A URL with a scheme, such as `https://example.com/setup`, does not start with `/`, and neither does a link to a
    heading of the same file, such as `#usage`, so neither is reported.

    ## Why is this bad?

    A path that starts with `/` is read from the root of the filesystem, or of the site that renders the file, never
    from the repository, so the link breaks wherever the files are checked out or installed. An agent that follows
    it reads a file the repository does not hold, or nothing.

    ## Example

    `docs/guide/setup.md`:

    ```markdown
    # Setup

    Every option is listed in [the configuration](/docs/guide/configuration.md).
    ```

    ## Use instead

    Spell the path relative to the file, as a document's links are read:

    ```markdown
    # Setup

    Every option is listed in [the configuration](configuration.md).
    ```

    Attributes:
        spec: Always `None`: the package states the rule.
        url: The link's destination as the Markdown parser encodes it, which the message shows percent-decoded.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 1)
    NAME: ClassVar[RuleName] = RuleName('absolute-link')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: ByMetaSpec(MetaSpecPart.STRUCTURE),
            ItemKind.META_SPEC: ByMetaSpec(MetaSpecPart.STRUCTURE),
            ItemKind.SKILL_ENTRYPOINT: ByPackage(),
            ItemKind.SKILL_RESOURCE: ByPackage(),
        }
    )

    spec: None = None
    url: str

    def message(self) -> str:
        """Name the link by its destination, percent-decoded as the author wrote it."""
        # The parser percent-encodes a destination, so `[x](</a b>)` arrives as `/a%20b`; the message shows `/a b`.
        return f'link `{unquote(self.url)}` is absolute'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say how to spell the link instead.

        A document's relative link is read from its own directory and a skill entrypoint's from the skill root, so
        the help
        names neither: it holds for any Markdown file.
        """
        return (Help('link by a relative path, which holds wherever the files are placed'),)

    @classmethod
    def query(cls) -> ItemQuery[tuple[Link, ...]]:
        """The links whose destination starts with `/`."""
        return absolute_links

    @classmethod
    def judge(cls, facts: tuple[Link, ...], /) -> tuple[Self, ...]:
        """One occurrence for each link or image whose destination starts with `/`, on its line, in document order.

        Args:
            facts: The absolute links of the file.
        """
        return tuple(cls(line=link.line, url=link.url) for link in facts)
