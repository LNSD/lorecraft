"""`LINK007`: two documents of different corpora link to each other."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Self
from urllib.parse import unquote

from lorecraft.project.corpus import CorpusName
from lorecraft.project.item import ItemKind
from lorecraft.project.link_target import DocumentLink
from lorecraft.project.query import ItemQuery, Primitives, item_corpus
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Note, Subdiagnostic
from lorecraft.rules.subject import BySpec, Facet, Gate, QueriedItemRule

from .__ruleset__ import GROUP_ID
from .queries import linked_documents


@dataclass(frozen=True, slots=True)
class MutualLinkFacts:
    """What a rule over links between corpora reads of the document.

    Attributes:
        corpus: The typed corpus the document lies in; `None` when it lies in none.
        links: The links to another document, with their corpus, filename and whether each links back.
    """

    corpus: CorpusName | None
    links: tuple[DocumentLink, ...]


def mutual_link_facts(primitives: Primitives) -> MutualLinkFacts:
    """The document's corpus and its links to other documents. Raises nothing.

    A query: it reads the document's corpus and its links with their back links and nothing else.

    Args:
        primitives: The model state of the document.
    """
    return MutualLinkFacts(corpus=primitives.query(item_corpus), links=primitives.query(linked_documents))


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MutualLink(QueriedItemRule[MutualLinkFacts]):
    """Two documents of different corpora link to each other.

    ## What it does

    Checks for a link from a document to a document of another corpus, `docs/<corpus>/<name>.md`, that links back to
    it. Both documents are reported, each on its own link, so either side sees the finding. A link to a document of
    the same corpus, to a file that is no document, to a missing file or to the document itself is not reported. No
    meta spec key states the rule: every document of a corpus that states a structure file is held to it.

    ## Why is this bad?

    Across corpora, one document builds on the other: a decision record on the requirement it answers, a feature
    document on the code rule it follows. The one that is built on stands without the other. A link in both
    directions makes each depend on the other, so neither can be read, changed or removed alone.

    ## Example

    `docs/arch/prd-001.md` and `docs/arch/../feat/guide.md`, each linking the other:

    ```markdown
    # Guide

    Read [the requirement](../arch/prd-001.md).
    ```

    ```markdown
    # Requirement

    The feature is described in [the guide](../feat/guide.md).
    ```

    ## Use instead

    Keep the link in the document that builds on the other, and drop it from the one built on:

    ```markdown
    # Requirement

    The feature is described by the guide that builds on it.
    ```

    Attributes:
        spec: Always `None`: the package states the rule.
        url: The link's destination as the Markdown parser encodes it, which the message shows percent-decoded.
        corpus: The corpus of the document the link leads to, such as `feat`.
        filename: The filename, with its extension, of the document the link leads to.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 7)
    NAME: ClassVar[RuleName] = RuleName('mutual-link')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('0.4.0')
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: BySpec(Facet.STRUCTURE),
        }
    )

    spec: None = None
    url: str
    corpus: str
    filename: str

    def message(self) -> str:
        """Name the destination, percent-decoded as the author wrote it, and the document that links back."""
        return f'`{unquote(self.url)}` leads to `{self.corpus}/{self.filename}`, which links back to this document'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Say what to do first, as no meta spec leads, then that documents of two corpora link one way."""
        return (
            Help(
                f'keep the link in the document that builds on the other, and remove it from `{self.filename}` or here'
            ),
            Note('documents of two corpora link one way: the one that builds on the other links it'),
        )

    @classmethod
    def query(cls) -> ItemQuery[MutualLinkFacts]:
        """The corpus of the document and its links to other documents."""
        return mutual_link_facts

    @classmethod
    def judge(cls, facts: MutualLinkFacts, /) -> tuple[Self, ...]:
        """One occurrence for each link to a document of another corpus that links back, in document order.

        Args:
            facts: The corpus of the document and the links to other documents it holds.
        """
        if facts.corpus is None:
            return ()
        return tuple(
            cls(line=link.line, url=link.url, corpus=str(link.corpus), filename=f'{link.filename}.md')
            for link in facts.links
            if link.has_back_link and link.corpus != facts.corpus
        )
