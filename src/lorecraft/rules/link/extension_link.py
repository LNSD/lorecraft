"""`LINK005`: a document links to a document that extends it."""

from dataclasses import dataclass
from typing import ClassVar, Self
from urllib.parse import unquote

from lorecraft.project.context import DocumentContext
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Note, Subdiagnostic
from lorecraft.rules.subject import DocumentRule, Facet

from .__ruleset__ import GROUP_ID


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class ExtensionLink(DocumentRule):
    """A document links to a document that extends it.

    ## What it does

    Checks for links and images in a document whose target lies in the same directory and whose filename continues
    the document's own name after a hyphen: `cli.md` linking to `cli-check.md`, or `feat.md` to `feat-cli.md`. The
    check reads every corpus, the specifications under `docs/__meta__/` included. No meta spec key states the
    rule: every document of a corpus that states a structure file is held to it.

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
    GOVERNED_BY: ClassVar[Facet] = Facet.STRUCTURE

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
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """One occurrence for each link to an existing document in the same directory that extends this one.

        Args:
            subject: The document whose relative links are judged by the filename each leads to.
        """
        base = f'{subject.filename()}.md'
        return tuple(
            cls(line=link.line, url=link.url, extension=link.extension, base=base) for link in subject.extension_links()
        )
