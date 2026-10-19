"""The rule base of each subject kind, whose queried rules judge the facts of a query, and the facets.

A rule picks its subject kind by deriving from that kind's base: `DocumentRule` over a document, `SkillRule` over a
skill. A rule over what any Markdown file has derives from `MarkdownRule` instead, and judges a document, a skill's
`SKILL.md` and a skill's resource alike; a rule over one of a skill's Markdown files derives from `SkillFileRule`, and
judges its `SKILL.md` and its resources alike, never a document; one over the frontmatter a document or a skill opens
with, which both kinds share, derives from `FrontmatterRule`. A rule derives from `Queried` and its subject-kind
base: it names a query and the runner hands `judge` the facts the query returns, so a rule never learns that a
database exists.

A document is judged only for what a meta spec governs, so a rule over a document declares the facet it reads in
`GOVERNED_BY`, and the runner hands it the document only when the meta specs govern that facet. A rule over the
frontmatter inherits `Facet.FRONTMATTER` from its base, which the runner gates it on over a document. A rule over a
Markdown file declares none: the base fixes the one facet it judges a document under, as its docstring states. The
package checks apply to skill entries independently of corpus governance. Resource Markdown checks are also package
checks, but a resource has no meta-spec structure governance.

A layout entry has a kind, and each kind has its base, which derives from `LayoutRule` rather than `ContentRule`, since
an entry has no lines and an occurrence points at the entry itself: `SymlinkRule` over a symlink of the skill layout
whose chain leaves the repository, `CorpusDirectoryRule` over a directory under `docs/` named like a reserved corpus.
The package governs the layout, so a rule over an entry declares no facet either.

Every rule derives from one of these bases: the length and the outline rules from `DocumentRule` or `SkillRule`, the
frontmatter rules from `FrontmatterRule` or, for those over a skill alone, from `SkillRule`, the link rules from
`MarkdownRule` and `SkillFileRule`, and layout rules from `QueriedSymlinkRule` or `QueriedCorpusDirectoryRule`,
which bind each layout kind to its matching query type.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import ClassVar, Self

from lorecraft.project.item import ItemKind
from lorecraft.project.query import CorpusDirectoryPrimitives, ItemQuery, Primitives, Query, SymlinkPrimitives
from lorecraft.schemas.types import SchemaReference

from .declaration import ContentRule, LayoutRule, Rule


class Facet(StrEnum):
    """What part of a document a meta spec governs, which a rule over a document or the frontmatter is gated on.

    Each member is one condition on the meta specs that govern a document, read before any rule over that facet
    runs. A document in no corpus, or in a corpus that states no structure file, is governed for none.
    """

    FRONTMATTER = 'frontmatter'
    """The document's frontmatter: a structure file that governs it states a frontmatter schema."""
    STRUCTURE = 'structure'
    """The document's structure: its corpus states a structure file."""
    OUTLINE = 'outline'
    """The document's sections: a structure file that governs it states an outline."""
    BUDGET = 'budget'
    """The document's length in tokens: a structure file that governs it sets a token budget."""


@dataclass(frozen=True, slots=True)
class BySpec:
    """A gate for an item facet a loaded structure layer may govern.

    Attributes:
        facet: The facet a loaded structure layer must state for the rule to judge the item.
        requires_loaded_layer: Whether a skill entry also requires loaded corpus governance for this rule.
    """

    facet: Facet
    requires_loaded_layer: bool = False


@dataclass(frozen=True, slots=True)
class ByPackage:
    """A gate for an item kind governed independently of a structure layer."""


@dataclass(frozen=True, slots=True)
class BySchema:
    """A gate for an item kind when its governing schema is registered.

    Attributes:
        schema: The registered schema that governs the item for this rule.
    """

    schema: SchemaReference


type Gate = BySpec | ByPackage | BySchema


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemRule(ContentRule):
    """The base of every rule over a Markdown item, with a gate for each kind it judges.

    Attributes:
        GATES: The item kinds a rule judges and the gate that admits each kind.
    """

    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType({})
    APPLIES_TO: ClassVar[frozenset[ItemKind]]


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentRule(ItemRule):
    """The base of every rule over a document.

    Attributes:
        GOVERNED_BY: The facet of the document the rule reads; the rule judges only a document governed for it.
            Left unbound here, so the registry rejects a rule that declares none.
    """

    GOVERNED_BY: ClassVar[Facet]
    APPLIES_TO: ClassVar[frozenset[ItemKind]] = frozenset({ItemKind.DOCUMENT})
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType({})

    def __init_subclass__(cls) -> None:
        """Set the document gate when a rule declares its governed facet.

        Args:
            cls: The document rule class being created.
        """
        super(DocumentRule, cls).__init_subclass__()
        facet = cls.__dict__.get('GOVERNED_BY')
        if isinstance(facet, Facet):
            cls.GATES = MappingProxyType({kind: BySpec(facet) for kind in cls.APPLIES_TO})


type SubjectQuery[Facts] = (
    Query[Primitives, Facts] | Query[SymlinkPrimitives, Facts] | Query[CorpusDirectoryPrimitives, Facts]
)


class Queried[Facts, QueryType](Rule, ABC):
    """The mixin of a rule that names the query it needs and judges its facts.

    The rule names its query in `query` and its `judge` takes the facts that query returns, both typed by the rule's
    type argument: a rule whose query returns `TitleFacts` derives from `QueriedDocumentRule[TitleFacts]`, and a
    query of another type fails the type check. The runner resolves the query through the database and hands the
    facts to `judge`, so the rule is coupled to the rest only through the model state its query reads.
    """

    __slots__ = ()

    @classmethod
    @abstractmethod
    def query(cls) -> QueryType:
        """The query whose answer `judge` takes; the same function every call, since the database memoizes by it."""

    @classmethod
    @abstractmethod
    def judge(cls, facts: Facts, /) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition, from the facts alone.

        Args:
            facts: The answer of the rule's query.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedItemRule[Facts](Queried[Facts, ItemQuery[Facts]], ItemRule):
    """The base of a rule over items that declares each kind and gate it judges.

    The rule names its query and declares its complete `GATES` mapping. Item kinds absent from that mapping are
    never judged. Layout rules use their separate queried bases because their query primitives differ.
    """

    @classmethod
    @abstractmethod
    def query(cls) -> ItemQuery[Facts]:
        """The query over an item's primitives whose answer `judge` takes."""


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedDocumentRule[Facts](Queried[Facts, ItemQuery[Facts]], DocumentRule):
    """The base of a rule over a document that names the query it needs and judges its facts.

    Its query is a pure function over the document's primitives, so a rule naming another subject kind's query fails
    the type check.
    """

    @classmethod
    @abstractmethod
    def query(cls) -> ItemQuery[Facts]:
        """The query over an item's primitives whose answer `judge` takes."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SkillRule(ItemRule):
    """The base of every rule over a skill; the package governs every skill, so the rule declares no facet."""

    APPLIES_TO: ClassVar[frozenset[ItemKind]] = frozenset({ItemKind.SKILL_ENTRY})
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType({ItemKind.SKILL_ENTRY: ByPackage()})


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedSkillRule[Facts](Queried[Facts, ItemQuery[Facts]], SkillRule):
    """The base of a rule over a skill that names the query it needs and judges its facts.

    It works as `QueriedDocumentRule` does, over a skill's primitives.
    """

    @classmethod
    @abstractmethod
    def query(cls) -> ItemQuery[Facts]:
        """The query over an item's primitives whose answer `judge` takes."""


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedDocumentSkillRule[Facts](QueriedDocumentRule[Facts], QueriedSkillRule[Facts]):
    """The base of a queried corpus rule that applies to documents and governed skill entries alike."""

    APPLIES_TO: ClassVar[frozenset[ItemKind]] = frozenset({ItemKind.DOCUMENT, ItemKind.SKILL_ENTRY})

    def __init_subclass__(cls) -> None:
        """Set both structure gates from the corpus rule's declared facet.

        Args:
            cls: The document-and-skill rule class being created.
        """
        super(QueriedDocumentSkillRule, cls).__init_subclass__()
        facet = cls.__dict__.get('GOVERNED_BY')
        if isinstance(facet, Facet):
            cls.GATES = MappingProxyType(
                {
                    ItemKind.DOCUMENT: BySpec(facet),
                    ItemKind.SKILL_ENTRY: BySpec(facet, requires_loaded_layer=True),
                }
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class MarkdownRule(ItemRule):
    """The base of every rule over one Markdown file: a document, a skill's `SKILL.md` or a skill's resource.

    The rule judges a document only when the document is governed for `Facet.STRUCTURE`, the facet under which its
    corpus states a structure file, since a document is otherwise governed for no facet at all. The base
    fixes that facet rather than letting the rule declare one in `GOVERNED_BY`: a facet only gates a document, and a
    rule that declared a narrower one, such as `Facet.BUDGET`, would still judge every skill and resource, so the
    declaration would say less than the rule does. Package Markdown checks apply to every skill and resource,
    independently of corpus governance; the model keeps both facets active for a resource.
    """

    APPLIES_TO: ClassVar[frozenset[ItemKind]] = frozenset(ItemKind)
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: BySpec(Facet.STRUCTURE),
            ItemKind.SPECIFICATION: BySpec(Facet.STRUCTURE),
            ItemKind.SKILL_ENTRY: ByPackage(),
            ItemKind.SKILL_RESOURCE: ByPackage(),
        }
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedMarkdownRule[Facts](Queried[Facts, ItemQuery[Facts]], MarkdownRule):
    """The base of a rule over a Markdown file that names the query it needs and judges its facts.

    It works as `QueriedDocumentRule` does, over the primitives of a document, a skill or a resource alike.
    """

    @classmethod
    @abstractmethod
    def query(cls) -> ItemQuery[Facts]:
        """The query over an item's primitives whose answer `judge` takes."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SkillFileRule(ItemRule):
    """The base of every rule over one of a skill's Markdown files: its `SKILL.md` or one of its resources.

    The rule judges what holds of a skill's files and not of a document, such as a relative link read from the skill
    root: a document's links are read from its own directory. This is a package check, so the rule declares no facet
    and applies independently of corpus governance.
    """

    APPLIES_TO: ClassVar[frozenset[ItemKind]] = frozenset({ItemKind.SKILL_ENTRY, ItemKind.SKILL_RESOURCE})
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {ItemKind.SKILL_ENTRY: ByPackage(), ItemKind.SKILL_RESOURCE: ByPackage()}
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedSkillFileRule[Facts](Queried[Facts, ItemQuery[Facts]], SkillFileRule):
    """The base of a rule over one of a skill's Markdown files that names the query it needs and judges its facts.

    It works as `QueriedDocumentRule` does, over the primitives of a skill's `SKILL.md` or a resource alike.
    """

    @classmethod
    @abstractmethod
    def query(cls) -> ItemQuery[Facts]:
        """The query over an item's primitives whose answer `judge` takes."""


@dataclass(frozen=True, slots=True, kw_only=True)
class SymlinkRule(LayoutRule):
    """The base of every rule over a symlink of the skill layout; the package governs it, so it declares no facet."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CorpusDirectoryRule(LayoutRule):
    """The base of every rule over a reserved-corpus directory; the package governs it, so it declares no facet."""


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedSymlinkRule[Facts](Queried[Facts, Query[SymlinkPrimitives, Facts]], SymlinkRule):
    """The base of a query-backed rule over a symlink of the skill layout."""

    @classmethod
    @abstractmethod
    def query(cls) -> Query[SymlinkPrimitives, Facts]:
        """The query over a symlink's model facts whose answer `judge` takes."""


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedCorpusDirectoryRule[Facts](Queried[Facts, Query[CorpusDirectoryPrimitives, Facts]], CorpusDirectoryRule):
    """The base of a query-backed rule over a reserved-corpus directory."""

    @classmethod
    @abstractmethod
    def query(cls) -> Query[CorpusDirectoryPrimitives, Facts]:
        """The query over a reserved-corpus directory's model facts whose answer `judge` takes."""


@dataclass(frozen=True, slots=True, kw_only=True)
class FrontmatterRule(ItemRule):
    """The base of every rule over the frontmatter a document or a skill opens with.

    One rule judges both kinds through the primitives their queries share, so its judgment is written once.

    Attributes:
        GOVERNED_BY: `Facet.FRONTMATTER`, bound here for every rule over the frontmatter.
    """

    GOVERNED_BY: ClassVar[Facet] = Facet.FRONTMATTER
    APPLIES_TO: ClassVar[frozenset[ItemKind]] = frozenset({ItemKind.DOCUMENT, ItemKind.SKILL_ENTRY})
    GATES: ClassVar[Mapping[ItemKind, Gate]] = MappingProxyType(
        {
            ItemKind.DOCUMENT: BySpec(Facet.FRONTMATTER),
            ItemKind.SKILL_ENTRY: BySpec(Facet.FRONTMATTER),
        }
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedFrontmatterRule[Facts](Queried[Facts, ItemQuery[Facts]], FrontmatterRule):
    """The base of a rule over a frontmatter that names the query it needs and judges its facts.

    It works as `QueriedDocumentRule` does, over the primitives of a document or a skill alike.
    """

    @classmethod
    @abstractmethod
    def query(cls) -> ItemQuery[Facts]:
        """The query over an item's primitives whose answer `judge` takes."""
