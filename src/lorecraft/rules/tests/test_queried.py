"""A queried rule is judged from its query by the runner, never through a context."""

import pytest

from lorecraft.rules.length.title_too_long import TitleTooLong


class TestCheck:
    def test_refuses_a_context(self) -> None:
        """Given a queried rule, when `check` is called with a context, then it raises: only the runner judges it."""
        with pytest.raises(TypeError, match='judged from its query by the runner'):
            TitleTooLong.check(object())
