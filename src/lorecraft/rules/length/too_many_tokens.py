"""`LEN001`: a document is longer than its token budget allows."""

from dataclasses import dataclass
from typing import ClassVar, Protocol, Self

from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.query import (
    CountPrimitives,
    GovernancePrimitives,
    ItemQuery,
    item_structure_specs,
    item_token_count,
)
from lorecraft.project.syntax import FIRST_LINE, TokenCount
from lorecraft.rules.collector import rule
from lorecraft.rules.identity import Level, Release, RuleCode, RuleName
from lorecraft.rules.location import Help, Here, Label, Note, Subdiagnostic
from lorecraft.rules.overrun import Overrun, find_overrun
from lorecraft.rules.subject import Facet, QueriedDocumentSkillRule

from .__ruleset__ import GROUP_ID, spec_note


@dataclass(frozen=True, slots=True)
class TokenBudget:
    """The token budget one structure specification sets.

    Attributes:
        spec: The structure file that sets the budget.
        tokens: The most tokens the document's whole file may hold.
    """

    spec: RootRelativePath
    tokens: NonZeroUnsignedInt


@dataclass(frozen=True, slots=True)
class TokenFacts:
    """Everything a rule over the token budget reads, so it judges without the document.

    Attributes:
        count: The tokens in the document's whole file; zero when no budget governs it, as nothing is counted then.
        budgets: The token budget each governing specification sets, in the order the specifications apply.
    """

    count: TokenCount
    budgets: tuple[TokenBudget, ...]


class _GovernanceCountPrimitives(GovernancePrimitives, CountPrimitives, Protocol):
    """The primitives the queries below read."""


def token_facts(primitives: _GovernanceCountPrimitives) -> TokenFacts:
    """The token budgets that govern the document and its token count. Raises nothing.

    A query: counting tokens is the costly step, so a document no budget governs is never counted.

    Args:
        primitives: The model state of the document.
    """
    budgets = tuple(
        TokenBudget(spec=spec.path, tokens=spec.tokens)
        for spec in primitives.query(item_structure_specs)
        if spec.tokens is not None
    )
    count = primitives.query(item_token_count) if budgets else TokenCount(UnsignedInt(0))
    return TokenFacts(count=count, budgets=budgets)


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TooManyTokens(QueriedDocumentSkillRule[TokenFacts]):
    """A document is longer than its token budget allows.

    ## What it does

    Checks for documents longer than the token budget their structure file sets with its `tokens` key.
    The whole file counts: frontmatter, code blocks and tables as much as prose.

    A document that more than one meta spec governs, such as a corpus and a namespace, must fit every budget
    they set, and is reported once for each budget it exceeds.

    ## Why is this bad?

    An agent loads the whole document into its context, so every token of it is one less for the task at hand, on
    every load.

    ## Example

    `docs/__meta__/guide.spec.json`:

    ```json
    {
      "tokens": 4000
    }
    ```

    `docs/guide/setup.md`, at 5200 tokens:

    ```markdown
    # Setup

    Install the toolkit, then run it once over the repository.

    ## Configuration

    Every option the configuration file accepts, with its default and an example:

    <!-- ... 5150 more tokens, one subsection per option -->
    ```

    ## Use instead

    Move what an agent needs only some of the time into a document of its own, and link to it:

    ```markdown
    # Setup

    Install the toolkit, then run it once over the repository.

    ## Configuration

    Every option the configuration file accepts is described in [configuration](configuration.md).
    ```

    Attributes:
        spec: The structure file that sets the exceeded budget; never `None`, since a meta spec sets
            every budget.
        overrun: The tokens in the document's whole file against the budget they exceed.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 1)
    NAME: ClassVar[RuleName] = RuleName('too-many-tokens')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GOVERNED_BY: ClassVar[Facet] = Facet.BUDGET

    spec: RootRelativePath
    overrun: Overrun

    def message(self) -> str:
        """Name the tokens found against the budget they exceed."""
        return f'too many tokens ({self.overrun.count} > {self.overrun.cap})'

    def labels(self) -> tuple[Label, ...]:
        """Say how far past the budget the document runs, on the line the occurrence is reported at."""
        return (Label(Here(self.line), f'tokens over the budget: {self.overrun.excess}'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the meta spec that sets the budget, say how to cut tokens, and how they are counted."""
        return (
            spec_note(self.spec),
            Help(
                'split the document, or move what an agent needs only some of the time into a document of its own '
                'and link to it'
            ),
            Note('tokens are counted as o200k_base over the whole file: frontmatter, code blocks and tables included'),
        )

    @classmethod
    def query(cls) -> ItemQuery[TokenFacts]:
        """The token budgets of the document and its token count."""
        return token_facts

    @classmethod
    def judge(cls, facts: TokenFacts, /) -> tuple[Self, ...]:
        """One occurrence for each budget the document exceeds, in the order the meta specs apply.

        A meta spec that sets no budget holds the document to none.

        Args:
            facts: The budgets that govern the document and the tokens in its whole file.
        """
        occurrences: list[Self] = []
        for budget in facts.budgets:
            overrun = find_overrun(facts.count, budget.tokens)
            if overrun is not None:
                occurrences.append(cls(spec=budget.spec, line=FIRST_LINE, overrun=overrun))
        return tuple(occurrences)
