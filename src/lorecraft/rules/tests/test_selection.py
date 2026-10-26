"""Selecting all rules or matching one exact rule code."""

from typing import Final

import pytest

from ..identity import RuleCode
from ..selection import AllRules, RuleSelection
from .sample_rules.token_count.any_tokens import AnyTokens
from .sample_rules.token_count.empty_document import EmptyDocument

SMP001: Final[RuleCode] = AnyTokens.CODE
SMP002: Final[RuleCode] = EmptyDocument.CODE


@pytest.mark.unit
class TestRuleSelection:
    def test_all_keeps_every_rule(self) -> None:
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset())

        assert selection.is_kept(SMP001)
        assert selection.is_kept(SMP002)

    def test_exact_code_keeps_only_that_rule(self) -> None:
        selection = RuleSelection(select=frozenset({SMP001}), ignore=frozenset())

        assert selection.is_kept(SMP001)
        assert not selection.is_kept(SMP002)

    def test_exact_ignore_removes_selected_rule(self) -> None:
        selection = RuleSelection(select=frozenset({AllRules()}), ignore=frozenset({SMP001}))

        assert not selection.is_kept(SMP001)
        assert selection.is_kept(SMP002)

    def test_empty_selection_keeps_no_rule(self) -> None:
        selection = RuleSelection(select=frozenset(), ignore=frozenset())

        assert not selection.is_kept(SMP001)
        assert not selection.is_kept(SMP002)
