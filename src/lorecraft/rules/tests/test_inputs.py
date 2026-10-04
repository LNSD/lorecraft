"""The input values a rule reads, and the bounds they hold at construction."""

from typing import Final

import pytest

from lorecraft.core.num import PositiveInt
from lorecraft.core.path import RootRelativePath

from ..inputs import Budget, TokenCountInput

SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
"""A structure specification that sets a budget."""


@pytest.mark.unit
class TestTokenCountInput:
    def test_construct_with_a_negative_token_count_raises_value_error(self) -> None:
        #: Given
        token_count = -1

        #: When
        with pytest.raises(ValueError, match='token_count must be at least 0, got -1') as exc_info:
            TokenCountInput(token_count=token_count, budgets=(Budget(tokens=PositiveInt(1), spec=SPEC),))

        #: Then
        assert '-1' in str(exc_info.value), 'the error names the value received'
