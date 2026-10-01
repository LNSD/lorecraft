"""The layout's scope over a real tree: every file and directory inside a skill, at any depth, through its links.

`take_snapshot` reads the tree with `SNAPSHOT_SCOPE`, the scope every command passes, and the database answers
from that one snapshot, so these see the layout, the scan and the scope query wired together: what the snapshot
holds inside a skill, and what `Database.is_in_scope` and `Database.find_real_file` say about a path there.
"""

from pathlib import Path, PurePosixPath
from typing import Final

import pytest

from lorecraft.checks import Database
from lorecraft.core.path import RootRelativePath
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.vfs import Link, Snapshot, take_snapshot

SKILL: Final[str] = '.agents/skills/review'


def _write(root: Path, relative: str, data: bytes = b'') -> None:
    """Write one file under the root, creating its parents.

    Args:
        root: Directory the file is written under, as the repository root.
        relative: Path of the file below `root`, with `/` separators.
        data: Bytes written to the file. Empty by default.
    """
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _file_paths(snapshot: Snapshot) -> set[RootRelativePath]:
    """Every path the snapshot holds a file's bytes at.

    Args:
        snapshot: The scan whose file records are read.
    """
    paths: set[RootRelativePath] = set()
    for file in snapshot.files:
        paths.add(file.path)
    return paths


@pytest.fixture(scope='function')
def skill_tree(tmp_path: Path) -> Path:
    """A repository whose one skill holds nested files and a link of every kind, returned as the root.

    The skill is `.agents/skills/review/`. It holds `references/a.md` and `references/deep/b.md`; `guides`, a
    link to `shared/guides/`, which holds `deeper/d.md`; `notes.md`, a link to the file `notes/e.md`; `up` in
    `references/`, a link back to the skill directory; and `outside`, an absolute link to a directory beside the
    root, which holds `f.md`. `src/tool.py` and `docs/feat/deep/a.md` sit where the scope does not reach.

    Args:
        tmp_path: Directory the repository and the directory outside it are created in.
    """
    root = tmp_path / 'repo'
    _write(root, f'{SKILL}/SKILL.md', b'---\nname: review\n---\n')
    _write(root, f'{SKILL}/references/a.md', b'# A\n')
    _write(root, f'{SKILL}/references/deep/b.md', b'# B\n')
    _write(root, 'shared/guides/deeper/d.md', b'# D\n')
    _write(root, 'notes/e.md', b'# E\n')
    _write(root, 'src/tool.py')
    _write(root, 'docs/feat/deep/a.md')
    _write(tmp_path, 'outside/f.md', b'# F\n')
    (root / SKILL / 'guides').symlink_to('../../../shared/guides')
    (root / SKILL / 'notes.md').symlink_to('../../../notes/e.md')
    (root / SKILL / 'references' / 'up').symlink_to('..')
    (root / SKILL / 'outside').symlink_to(tmp_path / 'outside')
    return root


@pytest.mark.it
class TestSnapshotScopeInsideASkill:
    def test_take_snapshot_reads_every_file_of_a_skill_at_any_depth(self, skill_tree: Path) -> None:
        #: Given
        expected = {
            RootRelativePath.parse(f'{SKILL}/SKILL.md'),
            RootRelativePath.parse(f'{SKILL}/references/a.md'),
            RootRelativePath.parse(f'{SKILL}/references/deep/b.md'),
            RootRelativePath.parse('shared/guides/deeper/d.md'),
            RootRelativePath.parse('notes/e.md'),
        }

        #: When
        snapshot = take_snapshot(skill_tree, SNAPSHOT_SCOPE)

        #: Then
        assert _file_paths(snapshot) == expected, (
            'every file of the skill is read, nested ones and those its links lead to, at their real paths'
        )

    def test_take_snapshot_records_a_link_leading_outside_the_root_without_following_it(self, skill_tree: Path) -> None:
        #: Given
        outside = skill_tree.parent / 'outside'

        #: When
        snapshot = take_snapshot(skill_tree, SNAPSHOT_SCOPE)

        #: Then
        assert Link(RootRelativePath.parse(f'{SKILL}/outside'), PurePosixPath(outside)) in snapshot.links, (
            'the link outside the repository is recorded as it is, absolute, and nothing behind it is read'
        )

    def test_take_snapshot_records_a_link_to_an_ancestor_inside_a_skill(self, skill_tree: Path) -> None:
        #: Given
        link = RootRelativePath.parse(f'{SKILL}/references/up')

        #: When
        snapshot = take_snapshot(skill_tree, SNAPSHOT_SCOPE)

        #: Then
        assert Link(link, PurePosixPath('..')) in snapshot.links, (
            'the link back to the skill directory is recorded, and the scan ends rather than looping through it'
        )

    def test_is_in_scope_with_a_file_two_levels_inside_a_skill_returns_true(self, skill_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse(f'{SKILL}/references/deep/absent.md')

        #: When
        in_scope = database.is_in_scope(path)

        #: Then
        assert in_scope is True, 'the skills directory is read with no depth limit, so references/deep/ is listed'

    def test_is_in_scope_in_a_directory_inside_a_skill_the_disk_lacks_returns_true(self, skill_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse(f'{SKILL}/scripts/nested/run.py')

        #: When
        in_scope = database.is_in_scope(path)

        #: Then
        assert in_scope is True, 'the scope is declared: a missing directory inside a skill is in it, its file missing'

    def test_is_in_scope_below_a_linked_directory_inside_a_skill_returns_true(self, skill_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse(f'{SKILL}/guides/deeper/absent.md')

        #: When
        in_scope = database.is_in_scope(path)

        #: Then
        assert in_scope is True, 'guides leads to shared/guides/, listed with no depth limit, deeper/ included'

    def test_is_in_scope_through_a_link_to_an_ancestor_inside_a_skill_returns_true(self, skill_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse(f'{SKILL}/references/up/references/deep/b.md')

        #: When
        in_scope = database.is_in_scope(path)

        #: Then
        assert in_scope is True, 'up leads back to the skill directory, so the path names references/deep/b.md there'

    def test_is_in_scope_through_a_link_leading_outside_the_root_returns_false(self, skill_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse(f'{SKILL}/outside/f.md')

        #: When
        in_scope = database.is_in_scope(path)

        #: Then
        assert in_scope is False, 'the scan never follows a link out of the repository, so nothing there is in scope'

    def test_is_in_scope_outside_every_root_returns_false(self, skill_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse('src/tool.py')

        #: When
        in_scope = database.is_in_scope(path)

        #: Then
        assert in_scope is False, 'no link inside the skill leads to src/, so it stays outside the scope'

    def test_is_in_scope_beyond_the_docs_depth_returns_false(self, skill_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse('docs/feat/deep/a.md')

        #: When
        in_scope = database.is_in_scope(path)

        #: Then
        assert in_scope is False, 'docs/ is still read one level deep, whatever the skills directories reach'

    def test_find_real_file_below_a_linked_directory_inside_a_skill_returns_the_real_file(
        self, skill_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse(f'{SKILL}/guides/deeper/d.md')

        #: When
        real_file = database.find_real_file(path)

        #: Then
        assert real_file == RootRelativePath.parse('shared/guides/deeper/d.md'), (
            'the file behind the link inside the skill is in the snapshot at its real path'
        )

    def test_find_real_file_with_a_link_to_a_file_inside_a_skill_returns_its_real_target(
        self, skill_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse(f'{SKILL}/notes.md')

        #: When
        real_file = database.find_real_file(path)

        #: Then
        assert real_file == RootRelativePath.parse('notes/e.md'), (
            'the link inside the skill is followed to the file it names, read at its real path'
        )

    def test_find_real_file_through_a_link_leading_outside_the_root_returns_none(self, skill_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse(f'{SKILL}/outside/f.md')

        #: When
        real_file = database.find_real_file(path)

        #: Then
        assert real_file is None, 'the file behind a link out of the repository was never read'
