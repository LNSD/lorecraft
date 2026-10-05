"""The input kinds a rule reads, each a frozen value with the rule base whose `check` takes it.

An input holds the facts the database's queries returned about one subject, the subject's identity values a rule
compares them with, such as a document's filename or the directory a skill is listed under, and the specifications
that govern them, in the package's own types; an input the package governs, such as a skill's line count, holds no
specification. A rule picks its input by deriving from that input's base, and receives the input and nothing else.
Building an input from the queries is the run's job, in `lorecraft.checks`, never this package's.
"""

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Final, Self

from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.schemas import FrontmatterProblem, SectionName
from lorecraft.project.syntax import (
    Heading,
    InvalidYamlFrontmatter,
    LineNumber,
    MissingFrontmatter,
    NonMappingFrontmatter,
)
from lorecraft.rules.declaration import ContentRule
from lorecraft.vfs import ResolvedPath


class InputKind(Enum):
    """The kind of input a rule reads: each member names one input type, which one rule base's `check` takes."""

    TOKEN_COUNT = 'token-count'
    """A document's whole-file token count, with the budgets that govern it: `TokenCountInput`."""
    LINE_COUNT = 'line-count'
    """A skill's whole-`SKILL.md` line count: `LineCountInput`."""
    FRONTMATTER_BLOCK = 'frontmatter-block'
    """A document's or a skill's frontmatter block, with the name it must carry: `FrontmatterBlockInput`."""
    SCHEMA_PROBLEMS = 'schema-problems'
    """What each frontmatter schema that governs a document or a skill rejects: `SchemaProblemsInput`."""
    HEADINGS = 'headings'
    """A document's headings, with what each structure specification that governs it states: `HeadingsInput`."""
    OUTLINE_DIVERGENCE = 'outline-divergence'
    """Where a document's sections first stop matching each outline that governs it: `OutlineDivergenceInput`."""


@dataclass(frozen=True, slots=True)
class Budget:
    """A token budget a structure specification sets.

    Attributes:
        tokens: The most tokens the whole file may cost an agent that loads it.
        spec: The structure specification file that sets the budget.
    """

    tokens: NonZeroUnsignedInt
    spec: RootRelativePath


@dataclass(frozen=True, slots=True)
class TokenCountInput:
    """A document's whole-file token count, with every token budget that governs it.

    Each budget applies on its own: a document governed by a corpus and a namespace specification has two budgets
    and must fit both. A specification that sets no budget is not among them, and a document no budget governs
    gets no input at all.

    Attributes:
        token_count: The `o200k_base` tokens in the document's whole file, frontmatter, code and tables included.
        budgets: One per structure specification that governs the document and sets a budget, in the order the
            specifications apply.
    """

    token_count: UnsignedInt
    budgets: tuple[Budget, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class TokenCountRule(ContentRule):
    """The base of every rule over a document's token count."""

    @classmethod
    @abstractmethod
    def check(cls, subject: TokenCountInput) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the document's token count.

        Args:
            subject: The token count judged, with the budgets that govern it.
        """


@dataclass(frozen=True, slots=True)
class LineCountInput:
    """A skill's whole-`SKILL.md` line count.

    The package governs it, so every skill whose `SKILL.md` decodes has one. The budget it is held to is the Agent
    Skills specification's, stated by the rule that reads it, not one a specification in the repository sets.

    Attributes:
        line_count: The lines in the skill's whole `SKILL.md`, frontmatter, code and blank lines included.
    """

    line_count: UnsignedInt


@dataclass(frozen=True, slots=True, kw_only=True)
class LineCountRule(ContentRule):
    """The base of every rule over a skill's line count."""

    @classmethod
    @abstractmethod
    def check(cls, subject: LineCountInput) -> tuple[Self, ...]:
        """Every occurrence of the rule's condition in the skill's line count.

        Args:
            subject: The line count judged.
        """


@dataclass(frozen=True, slots=True)
class DocumentFrontmatterOwner:
    """A document whose frontmatter a schema governs: the name its frontmatter must carry, and where it is governed.

    Attributes:
        filename: The document's filename, without its extension, which its frontmatter `name` must equal.
        spec: The structure specification of the document's corpus, whose frontmatter schema makes the document
            governed for its frontmatter. A namespace's schema only narrows the corpus's, so this one file is
            always the specification that states every rule over the block.
    """

    filename: AspectFilename
    spec: RootRelativePath


@dataclass(frozen=True, slots=True)
class SkillFrontmatterOwner:
    """A skill, whose frontmatter the package governs after the Agent Skills specification.

    Attributes:
        directory_name: The name of the skill directory as an agent lists it in its skills directory, which the
            frontmatter `name` must equal. An agent never resolves a link itself, so where a link leads plays no
            part in it.
        link_target: The resolved directory the listed directory leads to when it is a link, or `None` when it is
            not; it only words a note, so a reader sees why the name they know is not the one expected.
    """

    directory_name: str
    link_target: ResolvedPath | None


# Whose frontmatter block an input holds: a document a frontmatter schema governs, or a skill. A union of two
# records rather than one with a flag, so a document can never carry a link target, nor a skill a specification.
type FrontmatterOwner = DocumentFrontmatterOwner | SkillFrontmatterOwner


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
class StructureSpecSchema:
    """A frontmatter schema a structure specification states under its `frontmatter` key.

    Attributes:
        spec: The structure specification file that states the schema.
    """

    spec: RootRelativePath


@dataclass(frozen=True, slots=True)
class AgentSkillsSchema:
    """The Agent Skills specification's frontmatter schema: the package states it, and no repository file sets it."""


# The schema a set of problems was found against: one a structure specification file states, for a document, or
# the Agent Skills specification's, for a skill.
type SchemaSource = StructureSpecSchema | AgentSkillsSchema


@dataclass(frozen=True, slots=True)
class LocatedProblem:
    """One thing a frontmatter schema rejects, with the line it is reported on.

    Attributes:
        problem: What the schema rejects.
        line: The line of the field it concerns, or line 1 when it concerns no field or a field not written.
    """

    problem: FrontmatterProblem
    line: LineNumber


@dataclass(frozen=True, slots=True)
class SchemaProblems:
    """Every problem one frontmatter schema found in a frontmatter.

    Attributes:
        source: The schema the problems were found against.
        problems: In the order the schema reports them; empty when the frontmatter conforms to it.
    """

    source: SchemaSource
    problems: tuple[LocatedProblem, ...]


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


SECTION_LEVEL: Final[int] = 2
"""The heading level of a section: H1 is the title, and anything deeper is a subsection."""


@dataclass(frozen=True, slots=True)
class SectionCap:
    """The most prose words one section of a document may hold, under one structure specification.

    Attributes:
        section: The section's H2 heading, with the prose words the section holds, its subsections included.
        words: The cap: that of the outline entry naming the section, or, for a section the outline does not name,
            that of the `any` run it falls in.
    """

    section: Heading
    words: NonZeroUnsignedInt


@dataclass(frozen=True, slots=True)
class TitleCap:
    """The most words a document's title may hold, under one structure specification, against the words it holds.

    Attributes:
        title: The document's first H1 heading, its title; a later H1 is not its title, so no cap applies to it.
        title_words: The words of the title's own text, counted as a section's prose words are.
        words: The cap the specification's `title` sets.
    """

    title: Heading
    # Not range-checked: only the headings builder makes a cap, from `count_words`, so the value is never below 0.
    title_words: int
    words: NonZeroUnsignedInt


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
        title_cap: The cap on the title's words, measured against the document's title; or `None` when the
            specification sets no cap, or when the document has no title.
        title_mismatch: The title and the pattern its text does not match; or `None` when it matches, when the
            specification sets no pattern, or when the document has no title.
        forbid_empty_sections: True when every section must hold content.
        forbidden: The sections that must not appear at all, each named once, matched against the document's
            H2 headings alone: a deeper heading of the same text is a subsection, not a forbidden section.
        section_caps: One per H2 section of the document a word cap applies to, in document order; a section no
            cap applies to is not among them.
    """

    spec: RootRelativePath
    title_cap: TitleCap | None
    title_mismatch: TitleMismatch | None
    forbid_empty_sections: bool
    forbidden: tuple[SectionName, ...]
    section_caps: tuple[SectionCap, ...]


@dataclass(frozen=True, slots=True)
class HeadingsInput:
    """A document's headings, with what each structure specification that governs it states over them.

    Each specification applies on its own: a document governed by a corpus and a namespace specification has two
    entries and must pass both, since neither can relax the other. A document no structure specification governs
    gets no input at all.

    The title is the exception: no specification states it, since every governed document carries exactly one H1
    title that opens it. So a title rule judges the document once, under its corpus's structure specification,
    rather than once per specification. A check a specification adds on the title, a cap on its words or a pattern
    its text must match, is that specification's own, and applies once per specification that states it.

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
class DocumentEnd:
    """The end of a document, where a section the outline expects last would be written.

    Attributes:
        last_line: The document's last line, or line 1 for an empty document.
    """

    last_line: LineNumber


@dataclass(frozen=True, slots=True)
class AbsentSection:
    """A required section the outline expects next, which the document holds nowhere.

    Attributes:
        name: The section's heading text, as the outline entry names it.
        description: What the section holds, as the outline entry states it, or `None` when it states none.
        example: The first sample of the section's body the outline entry gives, without its heading, or `None`
            when it gives none.
        before: The section found where the missing one was expected, which it should come before; or the end of
            the document, when every section was matched before the outline expected it.
    """

    name: SectionName
    description: str | None
    example: str | None
    before: Heading | DocumentEnd


@dataclass(frozen=True, slots=True)
class MisplacedSection:
    """A section the outline names, written where the outline places a different section.

    Attributes:
        section: The section's H2 heading.
        expected: The section the outline places there instead, which the document holds later; or `None` when
            the section is left over once the outline is used up.
    """

    section: Heading
    expected: SectionName | None


@dataclass(frozen=True, slots=True)
class UnlistedSection:
    """A section the outline does not name, in a place no `any` run of the outline covers.

    Attributes:
        section: The section's H2 heading.
        expected: The section the outline places there instead, which the document holds later; or `None` when
            the section comes after the outline's end.
    """

    section: Heading
    expected: SectionName | None


# The first place a document's sections stop matching an outline: a required section absent from the document, a
# named section out of its place, or a section the outline does not name. Matching stops there, since every later
# entry would be compared with sections it was never meant to match.
type OutlineDivergence = AbsentSection | MisplacedSection | UnlistedSection


@dataclass(frozen=True, slots=True)
class OutlineDivergenceSpec:
    """Where a document's sections first stop matching one structure specification's outline.

    Attributes:
        spec: The structure specification file whose outline the sections are matched against.
        divergence: The first divergence, or `None` when the sections match the outline.
    """

    spec: RootRelativePath
    divergence: OutlineDivergence | None


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
