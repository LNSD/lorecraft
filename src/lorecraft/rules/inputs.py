"""The input kinds a rule reads, each a frozen value with the rule base whose `check` takes it.

An input holds the facts the database's queries returned about one document, and the specifications that govern
them, in types of `lorecraft.project` and the layers below it. A rule picks its input by deriving from that input's
base, and receives the input and nothing else. Building an input from the queries is the run's job, in
`lorecraft.checks`, never this package's.

The inputs are on their way out: the length rules, `LEN001` to `LEN005`, and the frontmatter rules, `FM001` to
`FM010`, read their subject through a context, from the bases in `subject`. The outline rules still read an input
here, and move onto a context in a later change, which removes this module.
"""

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.schemas import OutlineDivergenceSpec, SectionName
from lorecraft.project.syntax import Heading
from lorecraft.rules.declaration import ContentRule


class InputKind(Enum):
    """The kind of input a rule reads: each member names one input type, which one rule base's `check` takes."""

    HEADINGS = 'headings'
    """A document's headings, with what each structure specification that governs it states: `HeadingsInput`."""
    OUTLINE_DIVERGENCE = 'outline-divergence'
    """Where a document's sections first stop matching each outline that governs it: `OutlineDivergenceInput`."""


@dataclass(frozen=True, slots=True)
class TitleMismatch:
    """A document's title whose text does not match the pattern one structure specification holds it to.

    Attributes:
        title: The document's first H1 heading, its title; a later H1 is not its title, so no pattern applies to it.
        pattern: The pattern the title's text does not match, exactly as written; the input has already matched it, so
            a rule reads it only to give it.
    """

    title: Heading
    pattern: str


@dataclass(frozen=True, slots=True)
class HeadingsSpec:
    """What one structure specification states over a document's headings.

    Attributes:
        spec: The structure specification file that states it.
        title_mismatch: The title and the pattern its text does not match; or `None` when it matches, when the
            specification sets no pattern, or when the document has no title.
        forbid_empty_sections: True when every section must hold content.
        forbidden: The sections that must not appear at all, each named once, matched against the document's
            H2 headings alone: a deeper heading of the same text is a subsection, not a forbidden section.
    """

    spec: RootRelativePath
    title_mismatch: TitleMismatch | None
    forbid_empty_sections: bool
    forbidden: tuple[SectionName, ...]


@dataclass(frozen=True, slots=True)
class HeadingsInput:
    """A document's headings, with what each structure specification that governs it states over them.

    Each specification applies on its own: a document governed by a corpus and a namespace specification has two
    entries and must pass both, since neither can relax the other. A document no structure specification governs
    gets no input at all.

    The title is the exception: no specification states it, since every governed document carries exactly one H1
    title that opens it. So a title rule judges the document once, under its corpus's structure specification,
    rather than once per specification. A pattern a specification holds the title's text to is that specification's
    own, and applies once per specification that states it.

    The corpus's specification is held apart from the namespaces' so that a title rule finds it by name: a document
    governed by a namespace specification alone is ungoverned, so the corpus's is always there.

    Attributes:
        headings: The document's top-level headings, of every level, in document order.
        corpus: What the corpus's structure specification states, which the title rules report under.
        namespaces: What each matching namespace's structure specification states, broad to narrow; empty when no
            namespace specification governs the document.
    """

    headings: tuple[Heading, ...]
    corpus: HeadingsSpec
    namespaces: tuple[HeadingsSpec, ...]

    @property
    def specs(self) -> tuple[HeadingsSpec, ...]:
        """Every governing specification's entry, in the order the specifications apply: the corpus's first."""
        return (self.corpus, *self.namespaces)


@dataclass(frozen=True, slots=True, kw_only=True)
class HeadingsRule(ContentRule):
    """The base of every rule over a document's headings."""

    @classmethod
    @abstractmethod
    def check(cls, subject: HeadingsInput) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the document's headings.

        Args:
            subject: The headings judged, with what each governing structure specification states over them.
        """


@dataclass(frozen=True, slots=True)
class OutlineDivergenceInput:
    """Where a document's sections first stop matching each outline that governs them.

    Each specification applies on its own: a document governed by a corpus and a namespace specification that both
    state an outline has two entries and must match both. A specification with no outline is not among them, and a
    document no outline governs gets no input at all.

    Attributes:
        specs: One per structure specification that governs the document and states an outline, in the order the
            specifications apply.
    """

    specs: tuple[OutlineDivergenceSpec, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class OutlineDivergenceRule(ContentRule):
    """The base of every rule over where a document's sections stop matching their outlines."""

    @classmethod
    @abstractmethod
    def check(cls, subject: OutlineDivergenceInput) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition among the divergences the outlines found.

        Args:
            subject: The first divergence from each governing outline, if any.
        """
