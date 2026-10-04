"""The input kinds a rule reads, each a frozen value with the rule base whose `check` takes it.

An input holds the facts the database's queries returned about one subject and the specifications that govern
them, in the package's own types. A rule picks its input by deriving from that input's base, and receives the input
and nothing else. Building an input from the queries is the run's job, in `lorecraft.checks`, never this package's.
"""

from abc import abstractmethod
from dataclasses import dataclass
from typing import Self

from lorecraft.core.num import PositiveInt
from lorecraft.core.path import RootRelativePath
from lorecraft.rules.rule import ContentRule


@dataclass(frozen=True, slots=True)
class Budget:
    """A token budget a structure specification sets.

    Attributes:
        tokens: The most tokens the whole file may cost an agent that loads it.
        spec: The structure specification file that sets the budget.
    """

    tokens: PositiveInt
    spec: RootRelativePath


@dataclass(frozen=True, slots=True)
class TokenCountInput:
    """A document's whole-file token count, with every token budget that governs it.

    Each budget applies on its own: a document governed by a corpus and a namespace specification has two budgets
    and must fit both. A specification that sets no budget is not among them, and a document no budget governs
    gets no input at all.

    Attributes:
        token_count: The `o200k_base` tokens in the document's whole file, frontmatter, code and tables included; at
            least 0.
        budgets: One per structure specification that governs the document and sets a budget, in the order the
            specifications apply.
    """

    token_count: int
    budgets: tuple[Budget, ...]

    def __post_init__(self) -> None:
        """Validate the count's bound.

        Raises:
            ValueError: If `token_count` is negative.
        """
        if self.token_count < 0:
            raise ValueError(f'token_count must be at least 0, got {self.token_count}')


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
