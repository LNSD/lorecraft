"""The layout's guard: a view in which `docs/` or `docs/__meta__/` is a symlink is refused.

Each view answers from a hand-built snapshot, the shape a scan records.
"""

from pathlib import PurePosixPath

import pytest

from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.vfs import Link, Snapshot, VirtualFileSystem

from ..layout import DOCS_DIR, SPECS_DIR, LinkedLayoutError, require_real_layout


def _view_with_link(path: RootRelativePath, target: str) -> VirtualFileSystem:
    """A view over a snapshot holding one symlink and nothing else, which is all the guard reads.

    Args:
        path: Where the symlink sits in the snapshot.
        target: Where the symlink points, spelled as the link text.
    """
    return VirtualFileSystem(Snapshot(listings=(), files=(), links=(Link(path, PurePosixPath(target)),)))


@pytest.mark.unit
class TestRequireRealLayout:
    def test_require_real_layout_with_a_linked_specs_directory_raises_linked_layout_error(self) -> None:
        #: Given
        fs = _view_with_link(SPECS_DIR, '../specs')

        #: When
        with pytest.raises(LinkedLayoutError) as exc_info:
            require_real_layout(fs)

        #: Then
        assert isinstance(exc_info.value, Error), 'the error is one a command reports, not a crash'
        assert exc_info.value.path == SPECS_DIR, 'the error retains the directory that is a symlink'

    def test_require_real_layout_with_a_linked_docs_directory_raises_linked_layout_error(self) -> None:
        #: Given
        fs = _view_with_link(DOCS_DIR, 'documentation')

        #: When
        with pytest.raises(LinkedLayoutError) as exc_info:
            require_real_layout(fs)

        #: Then
        assert exc_info.value.path == DOCS_DIR, 'the error retains the directory that is a symlink'

    def test_require_real_layout_with_a_dangling_specs_link_raises_linked_layout_error(self) -> None:
        #: Given
        # A snapshot records a link's target unresolved, so a target that does not exist is a link all the same.
        fs = _view_with_link(SPECS_DIR, 'missing')

        #: When
        with pytest.raises(LinkedLayoutError) as exc_info:
            require_real_layout(fs)

        #: Then
        assert exc_info.value.path == SPECS_DIR, 'a link leading nowhere is refused like any other'

    def test_require_real_layout_with_real_directories_returns_without_raising(self) -> None:
        #: Given
        fs = VirtualFileSystem(
            Snapshot.from_files({SPECS_DIR / 'code.md': b'# Code\n', DOCS_DIR / 'code' / 'logging.md': b''})
        )

        #: When
        outcome = require_real_layout(fs)

        #: Then
        assert outcome is None, 'a layout of real directories is accepted'

    def test_require_real_layout_with_neither_directory_returns_without_raising(self) -> None:
        #: Given
        fs = VirtualFileSystem(Snapshot(listings=(), files=()))

        #: When
        outcome = require_real_layout(fs)

        #: Then
        assert outcome is None, 'a root that declares nothing is not a linked layout'

    def test_require_real_layout_with_a_linked_corpus_directory_returns_without_raising(self) -> None:
        #: Given
        fs = _view_with_link(DOCS_DIR / 'rules', 'code')

        #: When
        outcome = require_real_layout(fs)

        #: Then
        assert outcome is None, 'a linked corpus is left out by the model, not refused here'
