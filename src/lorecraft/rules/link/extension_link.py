"""`LINK005`: a document links to a document that extends it."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Self, assert_never
from urllib.parse import unquote

from lorecraft.project.item import ItemType
from lorecraft.project.link_target import DocumentDirectory, extension_links_of
from lorecraft.project.link_target import ExtensionLink as LinkToExtension
from lorecraft.project.query import ItemQuery, item_parse
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Note, Subdiagnostic
from lorecraft.rules.subject import Gate, QueriedItemRule, SpecPart, WhenSpec

from .__ruleset__ import GROUP_ID, GovernanceSyntaxLinkResolutionPrimitives
from .queries import ExtensionDocument, NotExtensionDocument, extension_document


@dataclass(frozen=True, slots=True)
class ExtensionLinkFacts:
    """What a rule over links to extensions reads of the document.

    Attributes:
        base: The filename, with its extension, of the document that holds the links.
        links: The links to an existing document beside it whose filename extends its own, in document order.
    """

    base: str
    links: tuple[LinkToExtension, ...]


def extension_link_facts(
    primitives: GovernanceSyntaxLinkResolutionPrimitives,
) -> ExtensionLinkFacts | NotExtensionDocument:
    """The links of a document to an existing document that extends it. Raises nothing.

    A query: it reads the item's links, their targets, their base and its name and nothing else. An item that is not a
    document has none.

    Args:
        primitives: The model state of the document.
    """
    document = primitives.query(extension_document)
    match document:
        case ExtensionDocument():
            pass
        case NotExtensionDocument():
            return document
        case _:
            assert_never(document)
    links = extension_links_of(
        primitives.query(item_parse).links,
        primitives.link_targets(),
        DocumentDirectory(document.directory),
        document.name,
    )
    return ExtensionLinkFacts(base=f'{document.name}.md', links=links)


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class ExtensionLink(QueriedItemRule[ExtensionLinkFacts | NotExtensionDocument]):
    """A document links to a document that extends it.

    ## What it does

    Checks for links and images in a document whose target lies in the same directory and whose filename continues
    the document's own name after a hyphen: `cli.md` linking to `cli-check.md`, or `feat.md` to `feat-cli.md`. The
    check reads every corpus and every spec of `docs/__meta__/`. No spec key states the rule:
    every document of a corpus that states a structure file, and every spec, is held to it.

    A document whose name is continued by another is that document's base, and the other is its extension. The
    extension names its base; the base never links to what extends it. Only a link to an existing file is
    reported, as a link to nothing is `LINK003`'s. A URL with a scheme, an absolute link and a fragment-only link
    spell no relative path, so none of them is reported.

    ## Why is this bad?

    A base is read on its own and stands for every extension that continues it. A link from the base to one of them
    makes the base depend on a document that depends on it, so the base grows with each extension added and a
    reader of the base is led into a specialisation they may not need.

    ## Example

    `docs/feat/cli.md`:

    ```markdown
    # CLI

    The checks live in [the check command](cli-check.md).
    ```

    ## Use instead

    Let the extension name its base, and leave the base without the link:

    ```markdown
    # CLI

    Each command has a document of its own.
    ```

    Attributes:
        spec: Always `None`: the package states the rule.
        url: The link's destination as the Markdown parser encodes it, which the message shows percent-decoded.
        extension: The filename, with its extension, of the document the link leads to.
        base: The filename, with its extension, of the document that holds the link, which `extension` continues.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 5)
    NAME: ClassVar[RuleName] = RuleName('extension-link')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('0.4.0')
    APPLIES_TO: ClassVar[Mapping[ItemType, Gate]] = MappingProxyType(
        {
            ItemType.DOCUMENT: WhenSpec(SpecPart.STRUCTURE),
            ItemType.SPEC: WhenSpec(SpecPart.STRUCTURE),
        }
    )

    spec: None = None
    url: str
    extension: str
    base: str

    def message(self) -> str:
        """Name the destination, percent-decoded as the author wrote it."""
        return f'`{unquote(self.url)}` leads to a document that extends this one'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say that the extension names its base and not the other way round, then what to do with the link."""
        return (
            Note(f'`{self.extension}` extends `{self.base}`: it names `{self.base}`, which names no extension'),
            Help(f'remove the link to `{self.extension}`'),
        )

    @classmethod
    def query(cls) -> ItemQuery[ExtensionLinkFacts | NotExtensionDocument]:
        """The links of the document to a document that extends it."""
        return extension_link_facts

    @classmethod
    def judge(cls, facts: ExtensionLinkFacts | NotExtensionDocument, /) -> tuple[Self, ...]:
        """One occurrence for each link to an existing document in the same directory that extends this one.

        Args:
            facts: The links to extensions and the filename of the document that holds them.
        """
        match facts:
            case ExtensionLinkFacts():
                return tuple(
                    cls(line=link.line, url=link.url, extension=str(link.extension), base=facts.base)
                    for link in facts.links
                )
            case NotExtensionDocument():
                return ()
            case _:
                assert_never(facts)
