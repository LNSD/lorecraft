"""What a document's structure specifications state about its title and its budget, as facts.

Each function reads the governing specifications or the parse tree once and returns a value a rule only projects, so no
rule unpacks a `Governance` or searches the headings itself.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import Heading, WordCount, count_words, find_title

from .structure import StructureSpec, TitleChecks


@dataclass(frozen=True, slots=True)
class DocumentTitle:
    """A document's title, and what is measured of its text.

    Attributes:
        heading: The title's heading, its first H1.
        chars: The Unicode code points in the title's text, inline markup stripped.
        words: The words in the title's text.
    """

    heading: Heading
    chars: UnsignedInt
    words: WordCount


@dataclass(frozen=True, slots=True)
class TitleConstraint:
    """The checks one structure specification holds the document's title to.

    Attributes:
        spec: The structure file that states the checks.
        checks: The caps and the pattern it states; at least one is set.
    """

    spec: RootRelativePath
    checks: TitleChecks


@dataclass(frozen=True, slots=True)
class TokenBudget:
    """The token budget one structure specification sets.

    Attributes:
        spec: The structure file that sets the budget.
        tokens: The most tokens the document's whole file may hold.
    """

    spec: RootRelativePath
    tokens: NonZeroUnsignedInt


def find_document_title(headings: Sequence[Heading]) -> DocumentTitle | None:
    """The document's title with its measures, or `None` when it has none. Raises nothing.

    Args:
        headings: The document's top-level headings, in document order.
    """
    heading = find_title(tuple(headings))
    if heading is None:
        return None
    return DocumentTitle(heading=heading, chars=UnsignedInt(len(heading.text)), words=count_words(heading.text))


def title_constraints(specs: Sequence[StructureSpec]) -> tuple[TitleConstraint, ...]:
    """The title checks each specification states, in the order the specifications apply. Raises nothing.

    Args:
        specs: The structure specifications that govern the document.
    """
    return tuple(TitleConstraint(spec=spec.path, checks=spec.title) for spec in specs if spec.title is not None)


def token_budgets(specs: Sequence[StructureSpec]) -> tuple[TokenBudget, ...]:
    """The token budget each specification sets, in the order the specifications apply. Raises nothing.

    Args:
        specs: The structure specifications that govern the document.
    """
    return tuple(TokenBudget(spec=spec.path, tokens=spec.tokens) for spec in specs if spec.tokens is not None)
