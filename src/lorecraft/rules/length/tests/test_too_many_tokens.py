"""`LEN001`, `too-many-tokens`, over a document's whole-file token count.

Every case is a document written as text, read through a fake context that counts its tokens as the real tokenizer
does, under structure files decoded from JSON; no document is read from disk.
"""

from typing import Final

import pytest

from lib.overruns import overrun
from lib.primitives import StructurePrimitives
from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber, TokenCount, count_tokens
from lorecraft.rules.location import Elsewhere, Help, Here, Label, Note
from lorecraft.rules.tests.fake_database import (
    FakeDocumentDatabase,
    judged,
    namespace_spec,
    structure_spec,
    structure_spec_path,
)

from ..too_many_tokens import TooManyTokens, token_facts

TEXT: Final[str] = '# Setup\n\nInstall the toolkit, then run it once over the repository.\n'
"""The document every case judges."""

TOKENS: Final[int] = count_tokens(TEXT).value
"""The tokens in `TEXT`, as the real tokenizer counts them."""

CORPUS_SPEC: Final[RootRelativePath] = structure_spec_path('code')
"""The corpus structure file, which sets one budget."""

NAMESPACE_SPEC: Final[RootRelativePath] = structure_spec_path('code-python')
"""A namespace structure file under the same corpus, which sets a budget of its own."""

NO_BUDGET: Final[str] = '{"empty_sections": "forbidden"}'
"""A structure file that states a rule other than a budget."""


def _budget(tokens: int) -> str:
    """A structure file that sets a token budget and nothing else.

    Args:
        tokens: The most tokens the meta spec lets a document it governs hold; at least 1.
    """
    return f'{{"tokens": {tokens}}}'


@pytest.mark.unit
class TestTooManyTokens:
    def test_check_with_a_document_over_the_budget_reports_it_on_line_1(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(TEXT, corpus='code', structure=_budget(TOKENS - 1))

        #: When
        occurrences = judged(TooManyTokens, subject)

        #: Then
        assert occurrences == (
            TooManyTokens(
                spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(1)), overrun=overrun(TOKENS, TOKENS - 1)
            ),
        ), 'a document over its budget is one occurrence, on line 1, naming the specification that sets the budget'

    def test_check_with_a_document_at_the_budget_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(TEXT, corpus='code', structure=_budget(TOKENS))

        #: When
        occurrences = judged(TooManyTokens, subject)

        #: Then
        assert occurrences == (), 'the budget is the most tokens allowed, so a document at the budget fits it'

    def test_check_with_a_document_over_only_the_namespace_budget_reports_that_budget(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(
            TEXT,
            corpus='code',
            structure=_budget(TOKENS + 10),
            namespaces=(namespace_spec('code', 'python', _budget(TOKENS - 1)),),
        )

        #: When
        occurrences = judged(TooManyTokens, subject)

        #: Then
        assert occurrences == (
            TooManyTokens(
                spec=NAMESPACE_SPEC, line=LineNumber(NonZeroUnsignedInt(1)), overrun=overrun(TOKENS, TOKENS - 1)
            ),
        ), 'a namespace budget does not replace the corpus one, so the document is held to it on its own'

    def test_check_with_a_document_over_both_budgets_reports_each_in_order(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(
            TEXT,
            corpus='code',
            structure=_budget(TOKENS - 1),
            namespaces=(namespace_spec('code', 'python', _budget(TOKENS - 2)),),
        )

        #: When
        occurrences = judged(TooManyTokens, subject)

        #: Then
        assert occurrences == (
            TooManyTokens(
                spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(1)), overrun=overrun(TOKENS, TOKENS - 1)
            ),
            TooManyTokens(
                spec=NAMESPACE_SPEC, line=LineNumber(NonZeroUnsignedInt(1)), overrun=overrun(TOKENS, TOKENS - 2)
            ),
        ), 'a document over two budgets is one occurrence per budget, in the order the specifications apply'

    def test_check_with_no_specification_setting_a_budget_reports_nothing(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(TEXT, corpus='code', structure=NO_BUDGET)

        #: When
        occurrences = judged(TooManyTokens, subject)

        #: Then
        assert occurrences == (), 'a document no specification sets a budget for is held to none'

    def test_check_with_a_specification_setting_no_budget_holds_the_document_to_the_other(self) -> None:
        #: Given
        subject = FakeDocumentDatabase(
            TEXT,
            corpus='code',
            structure=NO_BUDGET,
            namespaces=(namespace_spec('code', 'python', _budget(TOKENS - 1)),),
        )

        #: When
        occurrences = judged(TooManyTokens, subject)

        #: Then
        assert occurrences == (
            TooManyTokens(
                spec=NAMESPACE_SPEC, line=LineNumber(NonZeroUnsignedInt(1)), overrun=overrun(TOKENS, TOKENS - 1)
            ),
        ), 'a specification that sets no budget holds the document to none, and the one that sets a budget still does'

    def test_message_names_the_tokens_and_the_budget(self) -> None:
        #: Given
        occurrence = TooManyTokens(spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(1)), overrun=overrun(7, 6))

        #: When
        message = occurrence.message()

        #: Then
        assert message == 'too many tokens (7 > 6)', 'the message sets the token count against the budget'

    def test_labels_say_how_many_tokens_it_runs_over_the_budget(self) -> None:
        #: Given
        occurrence = TooManyTokens(spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(1)), overrun=overrun(7, 5))

        #: When
        labels = occurrence.labels()

        #: Then
        assert labels == (Label(Here(LineNumber(NonZeroUnsignedInt(1))), 'tokens over the budget: 2'),), (
            'the label sits on the reported line and gives the overrun'
        )

    def test_children_point_at_the_spec_then_help_then_say_how_tokens_are_counted(self) -> None:
        #: Given
        occurrence = TooManyTokens(spec=CORPUS_SPEC, line=LineNumber(NonZeroUnsignedInt(1)), overrun=overrun(7, 5))

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


@pytest.mark.unit
class TestTokenBudgets:
    def test_token_facts_keeps_the_order_and_skips_specifications_setting_none(self) -> None:
        #: Given
        corpus = structure_spec('code', '{"tokens": 100, "title": {"chars": 20}, "empty_sections": "forbidden"}')
        silent = structure_spec('code-silent', '{"outline": [{"section": "Rule"}]}')
        namespace = structure_spec('code-python', '{"tokens": 50, "title": {"words": 3}}')

        #: When
        budgets = token_facts(StructurePrimitives((corpus, silent, namespace))).budgets

        #: Then
        assert [(b.spec, b.tokens.value) for b in budgets] == [(corpus.path, 100), (namespace.path, 50)], (
            'one budget per specification that sets one'
        )

    def test_token_facts_of_no_specification_is_empty(self) -> None:
        #: When
        budgets = token_facts(StructurePrimitives(())).budgets

        #: Then
        assert budgets == (), 'nothing governs'


@pytest.mark.unit
class TestTokenCount:
    def test_token_facts_counts_tokens_only_when_a_budget_governs(self) -> None:
        #: Given
        budgeted = structure_spec('code', '{"tokens": 100}')
        silent = structure_spec('code-silent', '{"outline": [{"section": "Rule"}]}')
        count = TokenCount(UnsignedInt(7))

        #: When
        governed = token_facts(StructurePrimitives((budgeted,), token_total=count))
        ungoverned = token_facts(StructurePrimitives((silent,), token_total=count))

        #: Then
        assert (governed.count, ungoverned.count) == (count, UnsignedInt(0)), (
            'a document no budget governs is never counted'
        )
