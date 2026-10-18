"""Typed read keys for symlink and reserved-corpus directory queries."""

from pathlib import Path

import pytest

from lorecraft.project.database import Database, PrimitiveRead
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.query import SymlinkPrimitives
from lorecraft.project.skill import SymlinkRef
from lorecraft.vfs import RootExit, take_snapshot


def _symlink_exit(primitives: SymlinkPrimitives) -> RootExit:
    """The exit point recorded for a symlink subject."""
    return primitives.leaves_at()


def _database(root: Path) -> Database:
    """Build a real database containing a symlink layout subject."""
    files = {
        'docs/__meta__/code.md': b'# Code\n',
        'docs/__meta__/skills.md': b'# Skills\n',
        'docs/code/source.md': b'# Source\n',
        'docs/feat/target.md': b'# Target\n',
    }
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (root / 'docs' / 'skills').mkdir()
    outside = root.parent / f'{root.name}-outside'
    outside.mkdir()
    skill_links = root / '.agents' / 'skills'
    skill_links.mkdir(parents=True)
    (skill_links / 'outside').symlink_to(outside, target_is_directory=True)
    return Database.from_snapshot(take_snapshot(root, SNAPSHOT_SCOPE))


@pytest.mark.unit
class TestSubjectQueryReads:
    def test_query_records_a_symlink_subject_primitive(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        symlink = database.model().sorted_outside_symlinks[0]
        ref = SymlinkRef(symlink.path)

        #: When
        exit_point = database.query(_symlink_exit, ref)

        #: Then
        assert exit_point == symlink.leaves_at, 'the query returns the symlink exit recorded by the model'
        assert database.query_reads(_symlink_exit, ref) == {PrimitiveRead.SYMLINK_LEAVES_AT}, (
            'the read set identifies the symlink primitive'
        )
