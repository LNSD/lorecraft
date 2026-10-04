"""The layout's guard, and the scope a command naming directories to check the skills in declares.

A view in which `docs/` or `docs/__meta__/` is a symlink is refused; each view answers from a hand-built snapshot,
the shape a scan records. The scope is a value, compared whole.
"""

from pathlib import PurePosixPath

import pytest

from lorecraft.core.error import Error
from lorecraft.core.path import ROOT, RootRelativePath
from lorecraft.vfs import Link, ScanRoot, Snapshot, VirtualFileSystem

from ..layout import (
    DOCS_DIR,
    SNAPSHOT_SCOPE,
    SPECS_DIR,
    LinkedLayoutError,
    named_dirs_of_scope,
    reject_linked_layout,
    scope_with_named_dirs,
)


def _view_with_link(path: RootRelativePath, target: str) -> VirtualFileSystem:
    """A view over a snapshot holding one symlink and nothing else, which is all the guard reads.

    Args:
        path: Where the symlink sits in the snapshot.
        target: Where the symlink points, spelled as the link text.
    """
    return VirtualFileSystem(Snapshot(listings=(), files=(), links=(Link(path, PurePosixPath(target)),)))


@pytest.mark.unit
class TestRejectLinkedLayout:
    def test_reject_linked_layout_with_a_linked_specs_directory_raises_linked_layout_error(self) -> None:
        #: Given
        fs = _view_with_link(SPECS_DIR, '../specs')

        #: When
        with pytest.raises(LinkedLayoutError) as exc_info:
            reject_linked_layout(fs)

        #: Then
        assert isinstance(exc_info.value, Error), 'the error is one a command reports, not a crash'
        assert exc_info.value.path == SPECS_DIR, 'the error retains the directory that is a symlink'

    def test_reject_linked_layout_with_a_linked_docs_directory_raises_linked_layout_error(self) -> None:
        #: Given
        fs = _view_with_link(DOCS_DIR, 'documentation')

        #: When
        with pytest.raises(LinkedLayoutError) as exc_info:
            reject_linked_layout(fs)

        #: Then
        assert exc_info.value.path == DOCS_DIR, 'the error retains the directory that is a symlink'

    def test_reject_linked_layout_with_a_dangling_specs_link_raises_linked_layout_error(self) -> None:
        #: Given
        # A snapshot records a link's target unresolved, so a target that does not exist is a link all the same.
        fs = _view_with_link(SPECS_DIR, 'missing')

        #: When
        with pytest.raises(LinkedLayoutError) as exc_info:
            reject_linked_layout(fs)

        #: Then
        assert exc_info.value.path == SPECS_DIR, 'a link leading nowhere is refused like any other'

    def test_reject_linked_layout_with_real_directories_returns_without_raising(self) -> None:
        #: Given
        fs = VirtualFileSystem(
            Snapshot.from_tree({'docs': {'__meta__': {'code.md': b'# Code\n'}, 'code': {'logging.md': b''}}})
        )

        #: When
        outcome = reject_linked_layout(fs)

        #: Then
        assert outcome is None, 'a layout of real directories is accepted'

    def test_reject_linked_layout_with_neither_directory_returns_without_raising(self) -> None:
        #: Given
        fs = VirtualFileSystem(Snapshot(listings=(), files=()))

        #: When
        outcome = reject_linked_layout(fs)

        #: Then
        assert outcome is None, 'a root that declares nothing is not a linked layout'

    def test_reject_linked_layout_with_a_linked_corpus_directory_returns_without_raising(self) -> None:
        #: Given
        fs = _view_with_link(DOCS_DIR / 'rules', 'code')

        #: When
        outcome = reject_linked_layout(fs)

        #: Then
        assert outcome is None, 'a linked corpus is left out by the model, not refused here'


@pytest.mark.unit
class TestScopeWithNamedDirs:
    def test_scope_with_named_dirs_with_a_named_directory_reads_it_as_a_skills_directory(self) -> None:
        #: Given
        named_dirs = (RootRelativePath.parse('skills'),)

        #: When
        scope = scope_with_named_dirs(named_dirs)

        #: Then
        assert scope == (*SNAPSHOT_SCOPE, ScanRoot(RootRelativePath.parse('skills'), depth=None, follow_links=True)), (
            'the named directory joins the scope at any depth, its links followed'
        )

    def test_scope_with_named_dirs_with_no_named_directory_returns_the_snapshot_scope(self) -> None:
        #: Given
        named_dirs: tuple[RootRelativePath, ...] = ()

        #: When
        scope = scope_with_named_dirs(named_dirs)

        #: Then
        assert scope == SNAPSHOT_SCOPE, 'a command naming no directory reads what every command reads'

    def test_scope_with_named_dirs_with_an_agent_skills_directory_adds_no_root(self) -> None:
        #: Given
        named_dirs = (RootRelativePath.parse('.agents/skills'),)

        #: When
        scope = scope_with_named_dirs(named_dirs)

        #: Then
        assert scope == SNAPSHOT_SCOPE, 'a directory the scope already reads as a skills directory is not added again'

    def test_scope_with_named_dirs_with_the_root_adds_no_root(self) -> None:
        #: Given
        named_dirs = (ROOT,)

        #: When
        scope = scope_with_named_dirs(named_dirs)

        #: Then
        assert scope == SNAPSHOT_SCOPE, 'the root never joins: the snapshot would hold the whole repository'


@pytest.mark.unit
class TestNamedDirsOfScope:
    def test_named_dirs_of_scope_with_a_scope_naming_directories_returns_them_in_order(self) -> None:
        #: Given
        named_dirs = (RootRelativePath.parse('skills'), RootRelativePath.parse('vendor/skills'))
        scope = scope_with_named_dirs(named_dirs)

        #: When
        found = named_dirs_of_scope(scope)

        #: Then
        assert found == named_dirs, 'the roots beyond the snapshot scope are the directories named, in order'

    def test_named_dirs_of_scope_with_the_snapshot_scope_returns_empty(self) -> None:
        #: Given
        scope = SNAPSHOT_SCOPE

        #: When
        found = named_dirs_of_scope(scope)

        #: Then
        assert found == (), 'a scope naming no directory names none'
