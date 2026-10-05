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
from typing import Self

from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.syntax import InvalidYamlFrontmatter, LineNumber, MissingFrontmatter, NonMappingFrontmatter
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
