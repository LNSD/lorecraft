"""The `lock` fixture of the integration tests restores what it locked, whatever the order of the locks."""

from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.mark.it
class TestLockRestoresLockedPaths:
    def test_lock_with_a_child_locked_before_its_parent_restores_both_at_teardown(
        self, tmp_path: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        parent = tmp_path / 'parent'
        child = parent / 'child'
        child.mkdir(parents=True)

        #: When
        lock(child)
        lock(parent)

        #: Then
        assert not parent.stat().st_mode & 0o777, 'the parent refuses every access until teardown'
        # The restore runs at teardown: restoring the child first fails with `PermissionError` and errors this test.
