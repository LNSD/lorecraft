"""The layout's scope over a real tree: every file and directory inside a skill, at any depth, through its links.

`take_snapshot` reads the tree with `SNAPSHOT_SCOPE`, the scope every command passes, and the database answers
from that one snapshot, so these see the layout, the scan and the queries wired together: what the snapshot holds
inside a skill, what `Database.is_in_scope` and `Database.find_canonical_file` say about a path there, and which
resources `Database.skill_resources` lists for the skill and how `Database.skill_resource_parse` reads one.
"""

from pathlib import Path, PurePosixPath
from typing import Final

import pytest

from lorecraft.checks import Database
from lorecraft.core.path import RootRelativePath
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.skill import SkillRef, SkillResourceDecodeError, SkillResourceLocation, SkillResourceRef
from lorecraft.project.syntax import LineNumber
from lorecraft.project.syntax import Link as MarkdownLink
from lorecraft.vfs import Link, Snapshot, take_snapshot

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


def _skill_resource(path: str, resolves_to: str | None = None) -> SkillResourceLocation:
    """The location of a resource of the `review` skill.

    Args:
        path: Where an agent reaches the resource, root-relative.
        resolves_to: The canonical file it leads to; `path` itself when omitted.
    """
    canonical = path if resolves_to is None else resolves_to
    return SkillResourceLocation(
        SkillResourceRef(REVIEW, RootRelativePath.parse(path)), resolves_to=RootRelativePath.parse(canonical)
    )


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
            'every file of the skill is read, nested ones and those its links lead to, at their canonical paths'
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

    def test_find_canonical_file_below_a_linked_directory_inside_a_skill_returns_the_canonical_file(
        self, skill_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse(f'{SKILL}/guides/deeper/d.md')

        #: When
        canonical_file = database.find_canonical_file(path)

        #: Then
        assert canonical_file == RootRelativePath.parse('shared/guides/deeper/d.md'), (
            'the file behind the link inside the skill is in the snapshot at its canonical path'
        )

    def test_find_canonical_file_with_a_link_to_a_file_inside_a_skill_returns_its_canonical_target(
        self, skill_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse(f'{SKILL}/notes.md')

        #: When
        canonical_file = database.find_canonical_file(path)

        #: Then
        assert canonical_file == RootRelativePath.parse('notes/e.md'), (
            'the link inside the skill is followed to the file it names, read at its canonical path'
        )

    def test_find_canonical_file_through_a_link_leading_outside_the_root_returns_none(self, skill_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        path = RootRelativePath.parse(f'{SKILL}/outside/f.md')

        #: When
        canonical_file = database.find_canonical_file(path)

        #: Then
        assert canonical_file is None, 'the file behind a link out of the repository was never read'


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
            _skill_resource(f'{SKILL}/guides/deeper/d.md', 'shared/guides/deeper/d.md'),
            _skill_resource(f'{SKILL}/notes.md', 'notes/e.md'),
            _skill_resource(f'{SKILL}/references/a.md'),
            _skill_resource(f'{SKILL}/references/deep/b.md'),
        ), (
            'nested resources and those behind symlinks are listed under the skill, at their canonical files; the '
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
                SkillResourceRef(audit, RootRelativePath.parse('.agents/skills/audit/references/a.md')),
                resolves_to=RootRelativePath.parse('skills/audit/references/a.md'),
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

    def test_skill_resource_parse_of_a_resource_behind_a_symlinked_directory_parses_the_canonical_file(
        self, skill_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        ref = SkillResourceRef(REVIEW, RootRelativePath.parse(f'{SKILL}/guides/deeper/d.md'))

        #: When
        document = database.skill_resource_parse(ref)

        #: Then
        assert document.links == (MarkdownLink(url='../../SKILL.md', line=LineNumber(3)),), (
            'the ref names the resource through the symlink, and the tree is parsed from shared/guides/deeper/d.md'
        )

    def test_skill_resource_parse_called_twice_returns_the_first_answer(self, skill_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        ref = SkillResourceRef(REVIEW, RootRelativePath.parse(f'{SKILL}/references/a.md'))
        first = database.skill_resource_parse(ref)

        #: When
        second = database.skill_resource_parse(ref)

        #: Then
        assert second is first, 'a resource is parsed once per database, then shared by every check'

    def test_skill_resource_parse_of_a_resource_that_is_not_utf8_raises_skill_resource_decode_error(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, f'{SKILL}/SKILL.md', b'---\nname: review\n---\n')
        _write(tmp_path, f'{SKILL}/references/a.md', b'caf\xe9\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))
        ref = SkillResourceRef(REVIEW, RootRelativePath.parse(f'{SKILL}/references/a.md'))

        #: When
        with pytest.raises(SkillResourceDecodeError) as exc_info:
            database.skill_resource_parse(ref)

        #: Then
        assert exc_info.value.ref == ref, 'the error names the resource that could not be decoded'

    def test_skill_resource_parse_of_a_resource_the_skill_does_not_hold_raises_value_error(
        self, skill_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(skill_tree, SNAPSHOT_SCOPE))
        ref = SkillResourceRef(REVIEW, RootRelativePath.parse(f'{SKILL}/references/absent.md'))

        #: When
        with pytest.raises(ValueError) as exc_info:
            database.skill_resource_parse(ref)

        #: Then
        assert f'{SKILL}/references/absent.md' in str(exc_info.value), 'the error names the resource the skill lacks'
