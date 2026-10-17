"""The rule base of each subject kind, whose `check` reads the subject through its context, and the facets.

A rule picks its subject kind by deriving from that kind's base: `DocumentRule` over a document, `SkillRule` over a
skill. A rule over what any Markdown file has derives from `MarkdownRule` instead, and judges a document, a skill's
`SKILL.md` and a skill's resource alike; a rule over one of a skill's Markdown files derives from `SkillFileRule`, and
judges its `SKILL.md` and its resources alike, never a document; one over the frontmatter a document or a skill opens
with, which both kinds share, derives from `FrontmatterRule`. The base's abstract `check` takes the subject's
context, declared in `lorecraft.project`, and the rule asks it for the facts it reads and nothing else. The context
is answered by the database in `lorecraft.project.database`, so a rule never learns that a database exists.

A document is judged only for what a meta spec governs, so a rule over a document declares the facet it reads in
`GOVERNED_BY`, and the runner hands it the document only when the meta specs govern that facet. A rule over the
frontmatter inherits `Facet.FRONTMATTER` from its base, which the runner gates it on over a document. A rule over a
Markdown file declares none: the base fixes the one facet it judges a document under, as its docstring states. The
package governs every skill and every resource, so a rule over a skill or one of its files declares none either, and
a rule over the frontmatter or a Markdown file judges a skill whatever its facet.

A layout entry has a kind, and each kind has its base, which derives from `LayoutRule` rather than `ContentRule`, since
an entry has no lines and an occurrence points at the entry itself: `SymlinkRule` over a symlink of the skill layout
whose chain leaves the repository, `CorpusDirectoryRule` over a directory under `docs/` named like a reserved corpus.
The package governs the layout, so a rule over an entry declares no facet either.

Every rule derives from one of these bases: the length and the outline rules from `DocumentRule` or `SkillRule`, the
frontmatter rules from `FrontmatterRule` or, for those over a skill alone, from `SkillRule`, the link rules from
`MarkdownRule` and `SkillFileRule`, the symlink rule from `SymlinkRule` and the corpus directory rule from
`CorpusDirectoryRule`.
"""

from abc import abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Self

from lorecraft.project.context import (
    CorpusDirectoryContext,
    DocumentContext,
    FrontmatterContext,
    MarkdownContext,
    SkillContext,
    SkillFileContext,
    SymlinkContext,
)
from lorecraft.project.item import ItemKind
from lorecraft.project.schemas import Query

from .declaration import ContentRule, LayoutRule


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


@dataclass(frozen=True, slots=True, kw_only=True)
class ItemRule(ContentRule):
    """The base of every rule over a governed Markdown item, which binds the kinds of item the rule applies to.

    A run asks `applies_to` and `governing_facet` of a rule and never which base it derives from, so a rule of a new
    base needs no branch on where an item came from.

    Attributes:
        APPLIES_TO: The kinds of item the rule judges; a rule judges no item of another kind.
    """

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

    @classmethod
    @abstractmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the document.

        Args:
            subject: The document judged, governed for the rule's facet.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedDocumentRule[Facts](DocumentRule):
    """The base of a rule over a document that names the query it needs and judges its facts, never a context.

    The rule names its query in `query` and its `judge` takes the facts that query returns, both typed by the rule's
    type argument: a rule whose query returns `TitleFacts` derives from `QueriedDocumentRule[TitleFacts]`, and a
    query of another type fails the type check. The query is a pure function over the document's primitives, so the
    rule is coupled to the rest only through the model state it reads.
    """

    @classmethod
    @abstractmethod
    def query(cls) -> Query[Facts]:
        """The query whose answer `judge` takes; the same function every call, since the database memoizes by it."""

    @classmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """Resolve the query through the subject, then judge the facts it derives.

        Args:
            subject: The document judged, governed for the rule's facet.
        """
        return cls.judge(subject.query(cls.query()))

    @classmethod
    @abstractmethod
    def judge(cls, facts: Facts, /) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the document, from the facts alone.

        Args:
            facts: The answer of the rule's query.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class SkillRule(ItemRule):
    """The base of every rule over a skill; the package governs every skill, so the rule declares no facet."""

    APPLIES_TO: ClassVar[frozenset[ItemKind]] = frozenset({ItemKind.SKILL_ENTRY})

    @classmethod
    @abstractmethod
    def check(cls, subject: SkillContext) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the skill.

        Args:
            subject: The skill judged.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class QueriedSkillRule[Facts](SkillRule):
    """The base of a rule over a skill that names the query it needs and judges its facts, never a context.

    It works as `QueriedDocumentRule` does, over a skill's primitives.
    """

    @classmethod
    @abstractmethod
    def query(cls) -> Query[Facts]:
        """The query whose answer `judge` takes; the same function every call, since the database memoizes by it."""

    @classmethod
    def check(cls, subject: SkillContext) -> tuple[Self, ...]:
        """Resolve the query through the subject, then judge the facts it derives.

        Args:
            subject: The skill judged.
        """
        return cls.judge(subject.query(cls.query()))

    @classmethod
    @abstractmethod
    def judge(cls, facts: Facts, /) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the skill, from the facts alone.

        Args:
            facts: The answer of the rule's query.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class MarkdownRule(ItemRule):
    """The base of every rule over one Markdown file: a document, a skill's `SKILL.md` or a skill's resource.

    The rule judges a document only when the document is governed for `Facet.STRUCTURE`, the facet under which its
    corpus states a structure file, since a document is otherwise governed for no facet at all. The base
    fixes that facet rather than letting the rule declare one in `GOVERNED_BY`: a facet only gates a document, and a
    rule that declared a narrower one, such as `Facet.BUDGET`, would still judge every skill and resource, so the
    declaration would say less than the rule does. The package governs every skill and every resource.
    """

    APPLIES_TO: ClassVar[frozenset[ItemKind]] = frozenset(ItemKind)

    @classmethod
    @abstractmethod
    def check(cls, subject: MarkdownContext) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the Markdown file.

        Args:
            subject: The file judged: a document governed for its structure, a skill's `SKILL.md` or a resource.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class SkillFileRule(ItemRule):
    """The base of every rule over one of a skill's Markdown files: its `SKILL.md` or one of its resources.

    The rule judges what holds of a skill's files and not of a document, such as a relative link read from the skill
    root: a document's links are read from its own directory. The package governs every skill and every resource, so
    the rule declares no facet.
    """

    APPLIES_TO: ClassVar[frozenset[ItemKind]] = frozenset({ItemKind.SKILL_ENTRY, ItemKind.SKILL_RESOURCE})

    @classmethod
    @abstractmethod
    def check(cls, subject: SkillFileContext) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the skill's file.

        Args:
            subject: The file judged: a skill's `SKILL.md` or one of its resources.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class SymlinkRule(LayoutRule):
    """The base of every rule over a symlink of the skill layout; the package governs it, so it declares no facet."""

    @classmethod
    @abstractmethod
    def check(cls, subject: SymlinkContext) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition at the symlink.

        Args:
            subject: The symlink judged.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class CorpusDirectoryRule(LayoutRule):
    """The base of every rule over a directory under `docs/` named like a reserved corpus; it declares no facet."""

    @classmethod
    @abstractmethod
    def check(cls, subject: CorpusDirectoryContext) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition at the directory.

        Args:
            subject: The directory judged.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class FrontmatterRule(ItemRule):
    """The base of every rule over the frontmatter a document or a skill opens with.

    One rule judges both kinds through what their contexts share, so its check is written once.

    Attributes:
        GOVERNED_BY: `Facet.FRONTMATTER`, bound here for every rule over the frontmatter: a document is judged only
            when it is governed for it. The package governs every skill, so a skill is always judged. A skill's resource
            opens with no frontmatter the package governs, so the rule judges none.
    """

    GOVERNED_BY: ClassVar[Facet] = Facet.FRONTMATTER
    APPLIES_TO: ClassVar[frozenset[ItemKind]] = frozenset({ItemKind.DOCUMENT, ItemKind.SKILL_ENTRY})

    @classmethod
    @abstractmethod
    def check(cls, subject: FrontmatterContext) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the subject's frontmatter.

        Args:
            subject: The document or the skill judged; a document is governed for its frontmatter.
        """


def governing_facet(rule: type[ItemRule]) -> Facet | None:
    """The facet an item must be governed for before the rule judges it, or `None` when every item it applies to is.

    A rule over a document or the frontmatter declares it in `GOVERNED_BY`, and a rule over a Markdown file judges
    under `Facet.STRUCTURE`, as its base states. A rule over a skill or a skill's file reads no facet.

    Args:
        rule: The rule class.
    """
    if issubclass(rule, DocumentRule | FrontmatterRule):
        return rule.GOVERNED_BY
    if issubclass(rule, MarkdownRule):
        return Facet.STRUCTURE
    return None
