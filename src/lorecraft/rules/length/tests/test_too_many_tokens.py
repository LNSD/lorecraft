"""`LEN001`, `too-many-tokens`, over a document's whole-file token count.

Every case is a document written as text, read through a fake context that counts its tokens as the real tokenizer
does, under structure specifications decoded from JSON; no document is read from disk.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber, count_tokens
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note
from lorecraft.rules.tests.fake_context import FakeDocumentContext, namespace_spec, structure_spec_path

from ..too_many_tokens import TooManyTokens

TEXT: Final[str] = '# Setup\n\nInstall the toolkit, then run it once over the repository.\n'
"""The document every case judges."""

TOKENS: Final[int] = count_tokens(TEXT)
"""The tokens in `TEXT`, as the real tokenizer counts them."""

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('code')
"""The corpus structure specification, which sets one budget."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('code-python')
"""A namespace structure specification under the same corpus, which sets a budget of its own."""

NO_BUDGET: Final[str] = '{"empty_sections": "forbidden"}'
"""A structure specification that states a rule other than a budget."""


def _budget(tokens: int) -> str:
    """A structure specification that sets a token budget and nothing else.

    Args:
        tokens: The most tokens the specification lets a document it governs hold; at least 1.
    """
    return f'{{"tokens": {tokens}}}'


@pytest.mark.unit
class TestTooManyTokens:
    def test_check_with_a_document_over_the_budget_reports_it_on_line_1(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='code', structure=_budget(TOKENS - 1))

        #: When
        occurrences = TooManyTokens.check(subject)

        #: Then
        assert occurrences == (
            TooManyTokens(spec=CORPUS_SPEC, line=LineNumber.from_int(1), token_count=TOKENS, budget=TOKENS - 1),
        ), 'a document over its budget is one occurrence, on line 1, naming the specification that sets the budget'

    def test_check_with_a_document_at_the_budget_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='code', structure=_budget(TOKENS))

        #: When
        occurrences = TooManyTokens.check(subject)

        #: Then
        assert occurrences == (), 'the budget is the most tokens allowed, so a document at the budget fits it'

    def test_check_with_a_document_over_only_the_namespace_budget_reports_that_budget(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT,
            corpus='code',
            structure=_budget(TOKENS + 10),
            namespaces=(namespace_spec('code', 'python', _budget(TOKENS - 1)),),
        )

        #: When
        occurrences = TooManyTokens.check(subject)

        #: Then
        assert occurrences == (
            TooManyTokens(spec=NAMESPACE_SPEC, line=LineNumber.from_int(1), token_count=TOKENS, budget=TOKENS - 1),
        ), 'a namespace budget does not replace the corpus one, so the document is held to it on its own'

    def test_check_with_a_document_over_both_budgets_reports_each_in_order(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT,
            corpus='code',
            structure=_budget(TOKENS - 1),
            namespaces=(namespace_spec('code', 'python', _budget(TOKENS - 2)),),
        )

        #: When
        occurrences = TooManyTokens.check(subject)

        #: Then
        assert occurrences == (
            TooManyTokens(spec=CORPUS_SPEC, line=LineNumber.from_int(1), token_count=TOKENS, budget=TOKENS - 1),
            TooManyTokens(spec=NAMESPACE_SPEC, line=LineNumber.from_int(1), token_count=TOKENS, budget=TOKENS - 2),
        ), 'a document over two budgets is one occurrence per budget, in the order the specifications apply'

    def test_check_with_no_specification_setting_a_budget_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentContext(TEXT, corpus='code', structure=NO_BUDGET)

        #: When
        occurrences = TooManyTokens.check(subject)

        #: Then
        assert occurrences == (), 'a document no specification sets a budget for is held to none'

    def test_check_with_a_specification_setting_no_budget_holds_the_document_to_the_other(self) -> None:
        #: Given
        subject = FakeDocumentContext(
            TEXT,
            corpus='code',
            structure=NO_BUDGET,
            namespaces=(namespace_spec('code', 'python', _budget(TOKENS - 1)),),
        )

        #: When
        occurrences = TooManyTokens.check(subject)

        #: Then
        assert occurrences == (
            TooManyTokens(spec=NAMESPACE_SPEC, line=LineNumber.from_int(1), token_count=TOKENS, budget=TOKENS - 1),
        ), 'a specification that sets no budget holds the document to none, and the one that sets a budget still does'

    def test_message_with_an_occurrence_names_the_tokens_and_the_budget(self) -> None:
        #: Given
        occurrence = TooManyTokens(spec=CORPUS_SPEC, line=LineNumber.from_int(1), token_count=7, budget=6)

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'too many tokens (7 > 6)', 'the message sets the token count against the budget'

    def test_labels_with_an_occurrence_say_how_many_tokens_it_runs_over_the_budget(self) -> None:
        #: Given
        occurrence = TooManyTokens(spec=CORPUS_SPEC, line=LineNumber.from_int(1), token_count=7, budget=5)

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber.from_int(1)), 'tokens over the budget: 2'),), (
            'the label sits on the reported line and gives the overrun'
        )

    def test_children_with_an_occurrence_point_at_the_spec_then_help_then_say_how_tokens_are_counted(self) -> None:
        #: Given
        occurrence = TooManyTokens(spec=CORPUS_SPEC, line=LineNumber.from_int(1), token_count=7, budget=5)

        #: When
        children = occurrence.children()

        #: Then
        assert children == (
            Note('the limit is set here', at=Elsewhere(CORPUS_SPEC)),
            Help(
                'split the document, or move what an agent needs only some of the time into a document of its own '
                'and link to it'
            ),
            Note('tokens are counted as o200k_base over the whole file: frontmatter, code blocks and tables included'),
        ), 'the specification note comes first, then the help, then how the tokens are counted'
