"""The layout's scope over a real tree: every file and directory inside a skill, at any depth, through its links.

`take_snapshot` reads the tree with `SNAPSHOT_SCOPE`, the scope every command passes, and the database answers
from that one snapshot, so these see the layout, the scan and the queries wired together: what the snapshot holds
inside a skill, what `Database.is_in_scope` and `Database.find_file` say about a path there, and which
resources `Database.skill_resources` lists for the skill and how `Database.skill_resource_text` decodes one and
`Database.skill_resource_parse` parses it.
"""

from pathlib import Path, PurePosixPath
from typing import Final, assert_never

import pytest

from lorecraft.checks import Database, SkillResourceText, Undecodable
from lorecraft.core.path import RootRelativePath
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.skill import SkillRef, SkillRelativePath, SkillResourceLocation, SkillResourceRef
from lorecraft.project.syntax import LineNumber
from lorecraft.project.syntax import Link as MarkdownLink
from lorecraft.vfs import (
    DirectoryRecord,
    FileRecord,
    OtherRecord,
    ResolvedPath,
    Snapshot,
    SymlinkRecord,
    take_snapshot,
)

SKILL: Final[str] = '.agents/skills/review'
REVIEW: Final[SkillRef] = SkillRef(RootRelativePath.parse(SKILL))


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


def _skill_resource_text(database: Database, ref: SkillResourceRef) -> SkillResourceText:
    """The witness of a resource the test wrote as UTF-8, as the database decodes it.

    Args:
        database: The database the resource is decoded by.
        ref: A resource whose bytes are UTF-8.
    """
    source = database.skill_resource_text(ref)
    assert isinstance(source, SkillResourceText), f'{ref.path} was written as UTF-8, so it decodes'
    return source


def _skill_resource(path: str, resolves_to: str | None = None) -> SkillResourceLocation:
    """The location of a resource of the `review` skill.

    Args:
        path: Where an agent reaches the resource, spelled from the skill's directory.
        resolves_to: The resolved file it leads to, root-relative; `path` inside the skill's directory when omitted.
    """
    resolved = f'{SKILL}/{path}' if resolves_to is None else resolves_to
    return SkillResourceLocation(
        SkillResourceRef(REVIEW, SkillRelativePath.parse(path)),
        resolves_to=ResolvedPath(RootRelativePath.parse(resolved)),
    )


def _file_paths(snapshot: Snapshot) -> set[RootRelativePath]:
    """Every path the snapshot holds a file's bytes at.

    Args:
        snapshot: The scan whose file records are read.
    """
    paths: set[RootRelativePath] = set()
    for path, record in snapshot.records.items():
        match record:
            case FileRecord():
                paths.add(path)
            case DirectoryRecord() | SymlinkRecord() | OtherRecord():
                pass  # no bytes
            case _:
                assert_never(record)
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
    _write(root, 'shared/guides/deeper/d.md', b'# D\n\nSee [the skill](../../SKILL.md).\n')
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
            'every file of the skill is read, nested ones and those its links lead to, at their resolved paths'
        )

    def test_take_snapshot_records_a_link_leading_outside_the_root_without_following_it(self, skill_tree: Path) -> None:
        #: Given
        outside = skill_tree.parent / 'outside'

        #: When
        snapshot = take_snapshot(skill_tree, SNAPSHOT_SCOPE)

        #: Then
        assert snapshot.records[RootRelativePath.parse(f'{SKILL}/outside')] == SymlinkRecord(PurePosixPath(outside)), (
            'the link outside the repository is recorded as it is, absolute, and nothing behind it is read'
        )

    def test_take_snapshot_records_a_link_to_an_ancestor_inside_a_skill(self, skill_tree: Path) -> None:
        #: Given
        link = RootRelativePath.parse(f'{SKILL}/references/up')

        #: When
        snapshot = take_snapshot(skill_tree, SNAPSHOT_SCOPE)

        #: Then
        assert snapshot.records[link] == SymlinkRecord(PurePosixPath('..')), (
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

    def test_find_file_below_a_linked_directory_inside_a_skill_returns_the_resolved_file(
        self, skill_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse(f'{SKILL}/guides/deeper/d.md')

        #: When
        resolved_file = database.find_file(path)

        #: Then
        assert resolved_file == RootRelativePath.parse('shared/guides/deeper/d.md'), (
            'the file behind the link inside the skill is in the snapshot at its resolved path'
        )

    def test_find_file_with_a_link_to_a_file_inside_a_skill_returns_its_resolved_target(self, skill_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse(f'{SKILL}/notes.md')

        #: When
        resolved_file = database.find_file(path)

        #: Then
        assert resolved_file == RootRelativePath.parse('notes/e.md'), (
            'the link inside the skill is followed to the file it names, read at its resolved path'
        )

    def test_find_file_through_a_link_leading_outside_the_root_returns_none(self, skill_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse(f'{SKILL}/outside/f.md')

        #: When
        resolved_file = database.find_file(path)

        #: Then
        assert resolved_file is None, 'the file behind a link out of the repository was never read'


@pytest.mark.it
class TestDatabaseSkillResources:
    def test_skill_resources_of_a_skill_with_nested_files_and_symlinks_lists_every_resource(
        self, skill_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))

        #: When
        resources = database.skill_resources(REVIEW).resources

        #: Then
        assert resources == (
            _skill_resource('guides/deeper/d.md', 'shared/guides/deeper/d.md'),
            _skill_resource('notes.md', 'notes/e.md'),
            _skill_resource('references/a.md'),
            _skill_resource('references/deep/b.md'),
        ), (
            'nested resources and those behind symlinks are listed under the skill, at their resolved files; the '
            'symlink back to the skill adds nothing, and the one outside the root is left out'
        )

    def test_skill_resources_of_a_skill_whose_entry_is_a_symlink_names_them_under_the_entry(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'skills/audit/SKILL.md', b'---\nname: audit\n---\n')
        _write(tmp_path, 'skills/audit/references/a.md', b'# A\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'audit').symlink_to('../../skills/audit')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))
        audit = SkillRef(RootRelativePath.parse('.agents/skills/audit'))

        #: When
        resources = database.skill_resources(audit).resources

        #: Then
        assert resources == (
            SkillResourceLocation(
                SkillResourceRef(audit, SkillRelativePath.parse('references/a.md')),
                resolves_to=ResolvedPath(RootRelativePath.parse('skills/audit/references/a.md')),
            ),
        ), 'the walk starts where the model locates the entry, and names the resource under the entry'

    def test_skill_resources_called_twice_returns_the_first_answer(self, skill_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        first = database.skill_resources(REVIEW)

        #: When
        second = database.skill_resources(REVIEW)

        #: Then
        assert second is first, "a skill's resources are listed once per database, then shared by every check"

    def test_skill_resource_parse_of_a_resource_behind_a_symlinked_directory_parses_the_resolved_file(
        self, skill_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        ref = SkillResourceRef(REVIEW, SkillRelativePath.parse('guides/deeper/d.md'))
        source = _skill_resource_text(database, ref)

        #: When
        document = database.skill_resource_parse(source)

        #: Then
        assert document.links == (MarkdownLink(url='../../SKILL.md', line=LineNumber.from_int(3)),), (
            'the ref names the resource through the symlink, and the tree is parsed from shared/guides/deeper/d.md'
        )

    def test_skill_resource_parse_called_twice_returns_the_first_answer(self, skill_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        ref = SkillResourceRef(REVIEW, SkillRelativePath.parse('references/a.md'))
        source = _skill_resource_text(database, ref)
        first = database.skill_resource_parse(source)

        #: When
        second = database.skill_resource_parse(source)

        #: Then
        assert second is first, 'a resource is parsed once per database, then shared by every check'

    def test_skill_resource_text_of_a_resource_that_is_not_utf8_returns_undecodable(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, f'{SKILL}/SKILL.md', b'---\nname: review\n---\n')
        _write(tmp_path, f'{SKILL}/references/a.md', b'caf\xe9\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))
        ref = SkillResourceRef(REVIEW, SkillRelativePath.parse('references/a.md'))

        #: When
        source = database.skill_resource_text(ref)

        #: Then
        assert source == Undecodable(ref), 'a decode failure is an answer naming the resource, not an error'

    def test_skill_resource_text_of_a_resource_that_is_not_utf8_called_twice_returns_the_first_answer(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, f'{SKILL}/SKILL.md', b'---\nname: review\n---\n')
        _write(tmp_path, f'{SKILL}/references/a.md', b'caf\xe9\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))
        ref = SkillResourceRef(REVIEW, SkillRelativePath.parse('references/a.md'))
        first = database.skill_resource_text(ref)

        #: When
        second = database.skill_resource_text(ref)

        #: Then
        assert second is first, 'an undecodable resource is cached like any answer, so it is decoded once'

    def test_skill_resource_text_of_a_resource_the_skill_does_not_hold_raises_value_error(
        self, skill_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        ref = SkillResourceRef(REVIEW, SkillRelativePath.parse('references/absent.md'))

        #: When
        with pytest.raises(ValueError) as exc_info:
            database.skill_resource_text(ref)

        #: Then
        assert f'{SKILL}/references/absent.md' in str(exc_info.value), 'the error names the resource the skill lacks'
