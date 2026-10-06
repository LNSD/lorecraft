"""`LEN001`: a document is longer than its token budget allows."""

from dataclasses import dataclass
from typing import ClassVar, Final, Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.context import DocumentContext
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import Level, Release, RuleCode, RuleName, rule
from lorecraft.rules.location import Elsewhere, Note, Subdiagnostic
from lorecraft.rules.subject import DocumentRule, Facet

from .__ruleset__ import GROUP_ID

# A budget concerns the whole file, not one of its lines, but an occurrence under `ContentRule` carries a line, so
# it is reported at the first line.
_FIRST_LINE: Final[LineNumber] = LineNumber.from_int(1)
"""Where an occurrence is reported: the subject's first line."""


@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class TooManyTokens(DocumentRule):
    """A document is longer than its token budget allows.

    ## What it does

    Checks for documents longer than the token budget their structure specification sets with its `tokens` key.
    The whole file counts: frontmatter, code blocks and tables as much as prose.

    A document that more than one specification governs, such as a corpus and a namespace, must fit every budget
    they set, and is reported once for each budget it exceeds.

    ## Why is this bad?

    An agent loads the whole document into its context, so every token of it is one less for the task at hand, on
    every load.

    ## Example

    `docs/__meta__/guide.structure.json`:

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

    <!-- ... 1800 more tokens, one subsection per option -->
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
        spec: The structure specification that sets the exceeded budget; never `None`, since a specification sets
            every budget.
        token_count: The tokens in the document's whole file.
        budget: The budget it exceeds, in tokens.
    """

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 1)
    NAME: ClassVar[RuleName] = RuleName('too-many-tokens')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('0.3.0')
    GOVERNED_BY: ClassVar[Facet] = Facet.BUDGET

    spec: RootRelativePath
    token_count: int
    budget: int

    def message(self) -> str:
        """Name the tokens found against the budget they exceed."""
        return f'too many tokens ({self.token_count} > {self.budget})'

    def children(self) -> tuple[Subdiagnostic, ...]:
        """Point at the specification that sets the budget."""
        return (Note('the budget is set here', at=Elsewhere(self.spec)),)

    @classmethod
    def check(cls, subject: DocumentContext) -> tuple[Self, ...]:
        """One occurrence for each budget the document exceeds, in the order the specifications apply.

        A specification that sets no budget holds the document to none.

        Args:
            subject: The document, governed by at least one budget.
        """
        budgeted_specs = [spec for spec in subject.specifications().structure_specs() if spec.tokens is not None]
        if not budgeted_specs:
            # Counting tokens is the costly step, so a document no budget governs is never counted.
            return ()
        token_count = subject.tokens().value
        occurrences: list[Self] = []
        for structure_spec in budgeted_specs:
            budget = structure_spec.tokens
            if budget is not None and token_count > budget.value:
                occurrences.append(
                    cls(spec=structure_spec.path, line=_FIRST_LINE, token_count=token_count, budget=budget.value)
                )
        return tuple(occurrences)
