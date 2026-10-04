"""The input values a rule reads, and the bounds they hold at construction."""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath

from ..inputs import Budget, TokenCountInput

SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
"""A structure specification that sets a budget."""


@pytest.mark.unit
class TestBudget:
    def test_construct_with_zero_tokens_raises_value_error(self) -> None:
        #: Given
        tokens = 0

        #: When
        with pytest.raises(ValueError, match='tokens must be at least 1, got 0') as exc_info:
            Budget(tokens=tokens, spec=SPEC)

        #: Then
        assert '0' in str(exc_info.value), 'the error names the value received'


@pytest.mark.unit
class TestTokenCountInput:
    def test_construct_with_a_negative_token_count_raises_value_error(self) -> None:
        #: Given
        token_count = -1

        #: When
        with pytest.raises(ValueError, match='token_count must be at least 0, got -1') as exc_info:
            TokenCountInput(token_count=token_count, budgets=(Budget(tokens=1, spec=SPEC),))

        #: Then
        assert '-1' in str(exc_info.value), 'the error names the value received'
