"""The input kinds a rule reads, each a frozen value with the rule base whose `check` takes it.

An input holds the facts the database's queries returned about one subject, the subject's identity values a rule
compares them with, such as a document's filename or the directory a skill is listed under, and the specifications
that govern them, in types of `lorecraft.project` and the layers below it; an input the package governs, such as a
skill's frontmatter block, holds no specification. A rule picks its input by deriving from that input's base, and
receives the input and nothing else. Building an input from the queries is the run's job, in `lorecraft.checks`, never
this package's.

The inputs are on their way out: the length rules, `LEN001` to `LEN005`, read their subject through a context, from
the bases in `subject`. The frontmatter and outline rules still read an input here, and move onto a context in later
changes, which remove this module.
"""

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import FrontmatterOwner
from lorecraft.project.schemas import OutlineDivergenceSpec, SchemaProblems, SectionName
from lorecraft.project.syntax import (
    Heading,
    InvalidYamlFrontmatter,
    LineNumber,
    MissingFrontmatter,
    NonMappingFrontmatter,
)
from lorecraft.rules.declaration import ContentRule


class InputKind(Enum):
    """The kind of input a rule reads: each member names one input type, which one rule base's `check` takes."""

    FRONTMATTER_BLOCK = 'frontmatter-block'
    """A document's or a skill's frontmatter block, with the name it must carry: `FrontmatterBlockInput`."""
    SCHEMA_PROBLEMS = 'schema-problems'
    """What each frontmatter schema that governs a document or a skill rejects: `SchemaProblemsInput`."""
    HEADINGS = 'headings'
    """A document's headings, with what each structure specification that governs it states: `HeadingsInput`."""
    OUTLINE_DIVERGENCE = 'outline-divergence'
    """Where a document's sections first stop matching each outline that governs it: `OutlineDivergenceInput`."""


@dataclass(frozen=True, slots=True)
class NameField:
    """The top-level `name` a frontmatter mapping holds, and the line it is reported at.

    Frozen for equality only: a value of another type may be a list or a dict, so an instance may not be hashable.

    Attributes:
        value: The value as YAML decoded it, of whatever type it was written as.
        line: The line the `name` key is written on.
    """

    value: object
    line: LineNumber


@dataclass(frozen=True, slots=True)
class RepeatedKey:
    """One occurrence of a top-level key after its first.

    Attributes:
        key: The key, as YAML decoded it.
        line: The line this occurrence is written on.
        first_line: The line the key's first occurrence is written on, whichever occurrence this is.
    """

    key: str
    line: LineNumber
    first_line: LineNumber


@dataclass(frozen=True, slots=True)
class FrontmatterFields:
    """A frontmatter block that decoded to a mapping, as the rules over the block read it, each fact located.

    Attributes:
        name: The `name` the mapping holds, or `None` when it holds none.
        repeated_keys: Every top-level key written again, one per occurrence after the first, in document order.
    """

    name: NameField | None
    repeated_keys: tuple[RepeatedKey, ...]


# The frontmatter block of a subject, one member per outcome of reading it: no block, a block that is not YAML, a
# block that is not a mapping, or the mapping's located fields.
type FrontmatterBlock = MissingFrontmatter | InvalidYamlFrontmatter | NonMappingFrontmatter | FrontmatterFields


@dataclass(frozen=True, slots=True)
class FrontmatterBlockInput:
    """A document's or a skill's frontmatter block, with the name the subject must carry.

    A skill always has one, since the package governs every skill's frontmatter after the Agent Skills
    specification. A document has one only when a frontmatter schema governs it; one that no schema governs gets no
    input at all.

    Frozen for equality only: a `name` of another type may not be hashable, so neither is an instance.

    Attributes:
        frontmatter: The subject's frontmatter block, with every line a rule reports at already located.
        owner: The document or the skill the block opens, with the name its frontmatter must carry.
    """

    frontmatter: FrontmatterBlock
    owner: FrontmatterOwner


@dataclass(frozen=True, slots=True, kw_only=True)
class FrontmatterBlockRule(ContentRule):
    """The base of every rule over a document's or a skill's frontmatter block."""

    @classmethod
    @abstractmethod
    def check(cls, subject: FrontmatterBlockInput) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the frontmatter block.

        Args:
            subject: The frontmatter block judged, with the name its subject must carry.
        """


@dataclass(frozen=True, slots=True)
class SchemaProblemsInput:
    """What each frontmatter schema that governs a document or a skill rejects in its frontmatter.

    Every schema is applied on its own: a document governed by a corpus and a namespace schema has two entries and
    must conform to both. A skill has one entry, the Agent Skills specification's. A frontmatter block that is
    missing, unparseable or not a mapping is held to no schema, so its input has no entry: the block's own rules
    report it.

    Attributes:
        schemas: One per governing schema, in the order the schemas apply; empty when the block is not a mapping.
    """

    schemas: tuple[SchemaProblems, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class SchemaProblemsRule(ContentRule):
    """The base of every rule over what the frontmatter schemas reject."""

    @classmethod
    @abstractmethod
    def check(cls, subject: SchemaProblemsInput) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition among the problems the schemas found.

        Args:
            subject: The problems each governing schema found, each with its line.
        """


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
