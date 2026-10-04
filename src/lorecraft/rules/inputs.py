"""The input kinds a rule reads, each a frozen value with the rule base whose `check` takes it.

An input holds the facts the database's queries returned about one subject and the specifications that govern
them, in the package's own types; an input the package governs, such as a skill's line count, holds the facts
alone. A rule picks its input by deriving from that input's base, and receives the input and nothing else. Building
an input from the queries is the run's job, in `lorecraft.checks`, never this package's.
"""

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Self

from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import ContentRule


class InputKind(Enum):
    """The kind of input a rule reads: each member names one input type, which one rule base's `check` takes."""

    TOKEN_COUNT = 'token-count'
    """A document's whole-file token count, with the budgets that govern it: `TokenCountInput`."""
    LINE_COUNT = 'line-count'
    """A skill's whole-`SKILL.md` line count: `LineCountInput`."""


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
