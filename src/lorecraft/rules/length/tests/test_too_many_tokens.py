"""`LEN001`, `too-many-tokens`, over a document's whole-file token count.

The rule is pure, so every case here is a token count and the budgets that govern it; no document is read.
"""

from typing import Final

import pytest

from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.inputs import Budget, TokenCountInput
from lorecraft.rules.location import Elsewhere, Note

from ..too_many_tokens import TooManyTokens

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
"""A corpus structure specification, which sets one budget."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code-python.structure.json')
"""A namespace structure specification under the same corpus, which sets a budget of its own."""


@pytest.mark.unit
class TestTooManyTokens:
    def test_check_with_a_document_over_the_budget_reports_it_on_line_1(self) -> None:
        #: Given
        subject = TokenCountInput(
            token_count=UnsignedInt(7), budgets=(Budget(tokens=NonZeroUnsignedInt(6), spec=CORPUS_SPEC),)
        )

        #: When
        occurrences = TooManyTokens.check(subject)

        #: Then
        assert occurrences == (
            TooManyTokens(spec=CORPUS_SPEC, line=LineNumber.from_int(1), token_count=7, budget=6),
        ), 'a document over its budget is one occurrence, on line 1, naming the specification that sets the budget'

    def test_check_with_a_document_at_the_budget_reports_nothing(self) -> None:
        #: Given
        subject = TokenCountInput(
            token_count=UnsignedInt(7), budgets=(Budget(tokens=NonZeroUnsignedInt(7), spec=CORPUS_SPEC),)
        )

        #: When
        occurrences = TooManyTokens.check(subject)

        #: Then
        assert occurrences == (), 'the budget is the most tokens allowed, so a document at the budget fits it'

    def test_check_with_a_document_over_only_the_namespace_budget_reports_that_budget(self) -> None:
        #: Given
        subject = TokenCountInput(
            token_count=UnsignedInt(7),
            budgets=(
                Budget(tokens=NonZeroUnsignedInt(10), spec=CORPUS_SPEC),
                Budget(tokens=NonZeroUnsignedInt(5), spec=NAMESPACE_SPEC),
            ),
        )

        #: When
        occurrences = TooManyTokens.check(subject)

        #: Then
        assert occurrences == (
            TooManyTokens(spec=NAMESPACE_SPEC, line=LineNumber.from_int(1), token_count=7, budget=5),
        ), 'a namespace budget does not replace the corpus one, so the document is held to it on its own'

    def test_check_with_a_document_over_both_budgets_reports_each_in_order(self) -> None:
        #: Given
        subject = TokenCountInput(
            token_count=UnsignedInt(12),
            budgets=(
                Budget(tokens=NonZeroUnsignedInt(10), spec=CORPUS_SPEC),
                Budget(tokens=NonZeroUnsignedInt(5), spec=NAMESPACE_SPEC),
            ),
        )

        #: When
        occurrences = TooManyTokens.check(subject)

        #: Then
        assert occurrences == (
            TooManyTokens(spec=CORPUS_SPEC, line=LineNumber.from_int(1), token_count=12, budget=10),
            TooManyTokens(spec=NAMESPACE_SPEC, line=LineNumber.from_int(1), token_count=12, budget=5),
        ), 'a document over two budgets is one occurrence per budget, in the order the budgets are given'

    def test_message_with_an_occurrence_names_the_tokens_and_the_budget(self) -> None:
        #: Given
        occurrence = TooManyTokens(spec=CORPUS_SPEC, line=LineNumber.from_int(1), token_count=7, budget=6)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'too many tokens (7 > 6)', 'the message sets the token count against the budget'

    def test_children_with_an_occurrence_point_at_the_spec(self) -> None:
        #: Given
        occurrence = TooManyTokens(spec=CORPUS_SPEC, line=LineNumber.from_int(1), token_count=7, budget=5)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (Note('the budget is set here', at=Elsewhere(CORPUS_SPEC)),), (
            'a note points at the specification that sets the budget'
        )
