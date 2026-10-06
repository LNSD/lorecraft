"""The rule base of each subject kind, whose `check` reads the subject through its context, and the facets.

A rule picks its subject kind by deriving from that kind's base: `DocumentRule` over a document, `SkillRule` over a
skill. A rule over what any Markdown file has derives from `MarkdownRule` instead, and judges a document, a skill's
`SKILL.md` and a skill's resource alike. The base's abstract `check` takes the subject's context, declared in
`lorecraft.project`, and the rule asks it for the facts it reads and nothing else. The context is answered by the
database in `lorecraft.project.database`, so a rule never learns that a database exists.

A document is judged only for what a specification governs, so a rule over a document declares the facet it reads in
`GOVERNED_BY`, and the runner hands it the document only when the specifications govern that facet. A rule over a
Markdown file declares none: the base fixes the one facet it judges a document under, as its docstring states. The
package governs every skill and every resource, so a rule over a skill declares none either.

The token and line budgets, `LEN001` and `LEN002`, derive from these bases, and the link rules from `MarkdownRule`.
Until every group reads a context, the frontmatter, outline and other length rules still read the inputs of
`inputs`.
"""

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Self

from lorecraft.project.context import DocumentContext, MarkdownContext, SkillContext

from .declaration import ContentRule


class Facet(Enum):
    """What part of a document a specification governs, which a rule over a document declares it reads.

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
