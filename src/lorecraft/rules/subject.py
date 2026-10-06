"""The rule base of each subject kind, whose `check` reads the subject through its context, and the facets.

A rule picks its subject kind by deriving from that kind's base: `DocumentRule` over a document, `SkillRule` over a
skill. A rule over what any Markdown file has derives from `MarkdownRule` instead, and judges a document, a skill's
`SKILL.md` and a skill's resource alike; a rule over one of a skill's Markdown files derives from `SkillFileRule`, and
judges its `SKILL.md` and its resources alike, never a document; one over the frontmatter a document or a skill opens
with, which both kinds share, derives from `FrontmatterRule`. The base's abstract `check` takes the subject's
context, declared in `lorecraft.project`, and the rule asks it for the facts it reads and nothing else. The context
is answered by the database in `lorecraft.project.database`, so a rule never learns that a database exists.

A document is judged only for what a specification governs, so a rule over a document declares the facet it reads in
`GOVERNED_BY`, and the runner hands it the document only when the specifications govern that facet. A rule over the
frontmatter inherits `Facet.FRONTMATTER` from its base, which the runner gates it on over a document. A rule over a
Markdown file declares none: the base fixes the one facet it judges a document under, as its docstring states. The
package governs every skill and every resource, so a rule over a skill or one of its files declares none either, and
a rule over the frontmatter or a Markdown file judges a skill whatever its facet.

`LayoutEntryRule` is the base over a layout entry, one symlink of the skill layout whose chain leaves the repository.
A symlink has no lines, so the base derives from `LayoutRule` rather than `ContentRule`, and an occurrence points at
the entry itself. The package governs the skill layout, so a rule over it declares no facet either.

The length rules, `LEN001` to `LEN005`, the frontmatter rules, `FM001` to `FM010`, the link rules from `MarkdownRule`
and `SkillFileRule`, and `LAY001` from `LayoutEntryRule` derive from these bases. Until every group reads a context,
the outline rules still read the inputs of `inputs`.
"""

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Self

from lorecraft.project.context import (
    DocumentContext,
    FrontmatterContext,
    LayoutContext,
    MarkdownContext,
    SkillContext,
    SkillFileContext,
)

from .declaration import ContentRule, LayoutRule


class Facet(Enum):
    """What part of a document a specification governs, which a rule over a document or the frontmatter is gated on.

    Each member is one condition on the specifications that govern a document, read before any rule over that facet
    runs. A document in no corpus, or in a corpus that states no structure specification, is governed for none.
    """

    FRONTMATTER = 'frontmatter'
    """The document's frontmatter: a structure specification that governs it states a frontmatter schema."""
    STRUCTURE = 'structure'
    """The document's structure: its corpus states a structure specification."""
    OUTLINE = 'outline'
    """The document's sections: a structure specification that governs it states an outline."""
    BUDGET = 'budget'
    """The document's length in tokens: a structure specification that governs it sets a token budget."""


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentRule(ContentRule):
    """The base of every rule over a document.

    Attributes:
        GOVERNED_BY: The facet of the document the rule reads; the rule judges only a document governed for it.
            Left unbound here, so the registry rejects a rule that declares none.
    """

    GOVERNED_BY: ClassVar[Facet]

    @classmethod
    @abstractmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the document.

        Args:
            subject: The document judged, governed for the rule's facet.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class SkillRule(ContentRule):
    """The base of every rule over a skill; the package governs every skill, so the rule declares no facet."""

    @classmethod
    @abstractmethod
    def check(cls, subject: SkillContext) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the skill.

        Args:
            subject: The skill judged.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class MarkdownRule(ContentRule):
    """The base of every rule over one Markdown file: a document, a skill's `SKILL.md` or a skill's resource.

    The rule judges a document only when the document is governed for `Facet.STRUCTURE`, the facet under which its
    corpus states a structure specification, since a document is otherwise governed for no facet at all. The base
    fixes that facet rather than letting the rule declare one in `GOVERNED_BY`: a facet only gates a document, and a
    rule that declared a narrower one, such as `Facet.BUDGET`, would still judge every skill and resource, so the
    declaration would say less than the rule does. The package governs every skill and every resource.
    """

    @classmethod
    @abstractmethod
    def check(cls, subject: MarkdownContext) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the Markdown file.

        Args:
            subject: The file judged: a document governed for its structure, a skill's `SKILL.md` or a resource.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class SkillFileRule(ContentRule):
    """The base of every rule over one of a skill's Markdown files: its `SKILL.md` or one of its resources.

    The rule judges what holds of a skill's files and not of a document, such as a relative link read from the skill
    root: a document's links are read from its own directory. The package governs every skill and every resource, so
    the rule declares no facet.
    """

    @classmethod
    @abstractmethod
    def check(cls, subject: SkillFileContext) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the skill's file.

        Args:
            subject: The file judged: a skill's `SKILL.md` or one of its resources.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class LayoutEntryRule(LayoutRule):
    """The base of every rule over a layout entry; the package governs the skill layout, so it declares no facet."""

    @classmethod
    @abstractmethod
    def check(cls, subject: LayoutContext) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition at the layout entry.

        Args:
            subject: The layout entry judged.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class FrontmatterRule(ContentRule):
    """The base of every rule over the frontmatter a document or a skill opens with.

    One rule judges both kinds through what their contexts share, so its check is written once.

    Attributes:
        GOVERNED_BY: `Facet.FRONTMATTER`, bound here for every rule over the frontmatter: a document is judged only
            when it is governed for it. The package governs every skill, so a skill is always judged.
    """

    GOVERNED_BY: ClassVar[Facet] = Facet.FRONTMATTER

    @classmethod
    @abstractmethod
    def check(cls, subject: FrontmatterContext) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the subject's frontmatter.

        Args:
            subject: The document or the skill judged; a document is governed for its frontmatter.
        """
