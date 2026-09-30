"""Skill repository behavior against real skills directories.

The repository is wired to a real ``DiskFileSystem`` over ``tmp_path``, so entry kinds come from ``os.scandir``,
symlinks are followed by the operating system, and the error family comes from it refusing a read. Every path
it returns is root-relative to ``tmp_path``. The two skills directories are the ones this repository itself
carries: a universal one and an agent's own, linked to it.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest

from lorecraft.project.skill import ListSkillsError, Repository, ResolveSkillsDirError, SkillRef
from lorecraft.vfs import DiskFileSystem, RootRelativePath

UNIVERSAL_DIR: Final[RootRelativePath] = RootRelativePath.parse('.agents/skills')
CLAUDE_DIR: Final[RootRelativePath] = RootRelativePath.parse('.claude/skills')


@pytest.fixture(scope='function')
def repository(tmp_path: Path) -> Repository:
    """A repository over the temporary root; no skills directory exists until a test creates it."""
    return Repository(DiskFileSystem(tmp_path))


@pytest.fixture(scope='function')
def universal_dir(tmp_path: Path) -> Path:
    """An empty ``.agents/skills/`` under the temporary root."""
    directory = tmp_path / '.agents' / 'skills'
    directory.mkdir(parents=True)
    return directory


@pytest.fixture(scope='function')
def locked_universal_dir(universal_dir: Path) -> Iterator[Path]:
    """An ``.agents/skills/`` whose permissions refuse listing, restored afterwards so pytest can clean it up."""
    universal_dir.chmod(0o000)
    yield universal_dir
    universal_dir.chmod(0o700)


@pytest.fixture(scope='function')
def locked_skill_dir(universal_dir: Path) -> Iterator[Path]:
    """An ``.agents/skills/review/`` whose permissions refuse listing, restored afterwards for the cleanup."""
    directory = universal_dir / 'review'
    directory.mkdir()
    directory.chmod(0o000)
    yield directory
    directory.chmod(0o700)


def _write_skill(directory: Path) -> None:
    """Create ``directory`` and an empty ``SKILL.md`` in it: the repository never reads the file."""
    directory.mkdir(parents=True)
    (directory / 'SKILL.md').write_text('', encoding='utf-8')


def _ref(directory: str) -> SkillRef:
    return SkillRef(RootRelativePath.parse(directory))


@pytest.fixture(scope='function')
def locked_agents_dir(universal_dir: Path) -> Iterator[Path]:
    """An ``.agents/`` whose permissions refuse a search, restored afterwards so pytest can clean it up."""
    directory = universal_dir.parent
    directory.chmod(0o000)
    yield directory
    directory.chmod(0o700)


@pytest.mark.it
class TestRepositoryResolveSkillsDir:
    def test_resolve_skills_dir_with_a_regular_directory_returns_it(
        self, repository: Repository, universal_dir: Path
    ) -> None:
        #: Given
        skills_dir = UNIVERSAL_DIR

        #: When
        resolved = repository.resolve_skills_dir(skills_dir)

        #: Then
        assert universal_dir.is_dir(), 'the case turns on the skills directory existing'
        assert resolved == UNIVERSAL_DIR, 'a regular skills directory is its own real directory'

    def test_resolve_skills_dir_with_a_directory_linked_to_another_returns_the_other(
        self, tmp_path: Path, repository: Repository, universal_dir: Path
    ) -> None:
        #: Given
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')

        #: When
        resolved = repository.resolve_skills_dir(CLAUDE_DIR)

        #: Then
        assert universal_dir.is_dir(), 'the case turns on the link leading to a directory'
        assert resolved == UNIVERSAL_DIR, 'a linked skills directory resolves to the directory it leads to'

    def test_resolve_skills_dir_with_no_such_directory_returns_none(
        self, tmp_path: Path, repository: Repository
    ) -> None:
        #: Given
        # nothing is created under the temporary root
        missing_skills_dir = tmp_path / '.claude' / 'skills'

        #: When
        resolved = repository.resolve_skills_dir(CLAUDE_DIR)

        #: Then
        assert not missing_skills_dir.exists(), 'the case turns on the skills directory being absent'
        assert resolved is None, 'a repository without the directory has no such skills directory'

    def test_resolve_skills_dir_with_a_dangling_link_returns_none(self, tmp_path: Path, repository: Repository) -> None:
        #: Given
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')

        #: When
        resolved = repository.resolve_skills_dir(CLAUDE_DIR)

        #: Then
        assert resolved is None, 'a link that leads to no directory is not a skills directory'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_resolve_skills_dir_with_an_unsearchable_parent_raises_resolve_skills_dir_error(
        self, repository: Repository, locked_agents_dir: Path
    ) -> None:
        #: Given
        locked = locked_agents_dir

        #: When
        with pytest.raises(ResolveSkillsDirError) as exc_info:
            repository.resolve_skills_dir(UNIVERSAL_DIR)

        #: Then
        assert f'{locked.name}/skills' in str(exc_info.value), 'the error names the directory it could not resolve'


@pytest.mark.it
class TestRepositoryListSkills:
    def test_list_skills_with_two_skills_returns_them_sorted_by_directory(
        self, repository: Repository, universal_dir: Path
    ) -> None:
        #: Given
        _write_skill(universal_dir / 'review')
        _write_skill(universal_dir / 'commit')

        #: When
        skills = repository.list_skills(UNIVERSAL_DIR)

        #: Then
        assert skills == (_ref('.agents/skills/commit'), _ref('.agents/skills/review')), (
            'each directory holding a SKILL.md is a skill, listed in directory order'
        )

    def test_list_skills_with_a_linked_skill_entry_returns_the_entry_under_the_skills_directory(
        self, tmp_path: Path, repository: Repository, universal_dir: Path
    ) -> None:
        #: Given
        _write_skill(tmp_path / 'skills' / 'review')
        (universal_dir / 'review').symlink_to('../../skills/review')

        #: When
        skills = repository.list_skills(UNIVERSAL_DIR)

        #: Then
        assert skills == (_ref('.agents/skills/review'),), (
            'the skill is the entry under the skills directory, not the place its link leads to'
        )

    def test_list_skills_with_two_entries_leading_to_one_directory_returns_both_entries(
        self, repository: Repository, universal_dir: Path
    ) -> None:
        #: Given
        _write_skill(universal_dir / 'review')
        (universal_dir / 'audit').symlink_to('review')

        #: When
        skills = repository.list_skills(UNIVERSAL_DIR)

        #: Then
        assert skills == (_ref('.agents/skills/audit'), _ref('.agents/skills/review')), (
            'each entry under the skills directory is a skill of its own, as an agent sees them'
        )

    def test_list_skills_with_a_directory_without_a_skill_file_leaves_it_out(
        self, repository: Repository, universal_dir: Path
    ) -> None:
        #: Given
        (universal_dir / 'drafts').mkdir()
        (universal_dir / 'drafts' / 'README.md').write_text('', encoding='utf-8')

        #: When
        skills = repository.list_skills(UNIVERSAL_DIR)

        #: Then
        assert skills == (), 'a directory with no SKILL.md is not a skill'

    def test_list_skills_with_a_skill_file_directly_in_the_skills_directory_leaves_it_out(
        self, repository: Repository, universal_dir: Path
    ) -> None:
        #: Given
        (universal_dir / 'SKILL.md').write_text('', encoding='utf-8')

        #: When
        skills = repository.list_skills(UNIVERSAL_DIR)

        #: Then
        assert skills == (), 'a skill is a directory inside a skills directory, never the skills directory itself'

    def test_list_skills_with_a_nested_skill_directory_leaves_it_out(
        self, repository: Repository, universal_dir: Path
    ) -> None:
        #: Given
        _write_skill(universal_dir / 'group' / 'review')

        #: When
        skills = repository.list_skills(UNIVERSAL_DIR)

        #: Then
        assert skills == (), 'only an entry directly inside a skills directory is looked at'

    def test_list_skills_with_a_symlinked_skill_file_leaves_it_out(
        self, tmp_path: Path, repository: Repository, universal_dir: Path
    ) -> None:
        #: Given
        (tmp_path / 'REVIEW.md').write_text('', encoding='utf-8')
        (universal_dir / 'review').mkdir()
        (universal_dir / 'review' / 'SKILL.md').symlink_to('../../../REVIEW.md')

        #: When
        skills = repository.list_skills(UNIVERSAL_DIR)

        #: Then
        assert skills == (), 'only a regular SKILL.md makes a directory a skill'

    def test_list_skills_with_a_dangling_skill_entry_leaves_it_out(
        self, repository: Repository, universal_dir: Path
    ) -> None:
        #: Given
        (universal_dir / 'review').symlink_to('../../skills/review')

        #: When
        skills = repository.list_skills(UNIVERSAL_DIR)

        #: Then
        assert skills == (), 'a link that leads to no directory is not a skill and does not fail the listing'

    def test_list_skills_with_a_skill_entry_linked_outside_the_root_leaves_it_out(self, tmp_path: Path) -> None:
        #: Given
        # the root is a directory inside the temporary one, so a sibling of it is outside the root
        root = tmp_path / 'repository'
        (root / '.agents' / 'skills').mkdir(parents=True)
        _write_skill(tmp_path / 'elsewhere' / 'review')
        (root / '.agents' / 'skills' / 'review').symlink_to(tmp_path / 'elsewhere' / 'review')
        repository = Repository(DiskFileSystem(root))

        #: When
        skills = repository.list_skills(UNIVERSAL_DIR)

        #: Then
        assert skills == (), 'a skill outside the root has no root-relative path to be listed at'

    def test_list_skills_with_no_skills_directory_returns_empty(self, tmp_path: Path, repository: Repository) -> None:
        #: Given
        # nothing is created under the temporary root
        missing_skills_dir = tmp_path / '.agents' / 'skills'

        #: When
        skills = repository.list_skills(UNIVERSAL_DIR)

        #: Then
        assert not missing_skills_dir.exists(), 'the case turns on the skills directory being absent'
        assert skills == (), 'a missing skills directory has no skills rather than failing'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_list_skills_with_an_unreadable_skills_directory_raises_list_skills_error(
        self, repository: Repository, locked_universal_dir: Path
    ) -> None:
        #: Given
        locked = locked_universal_dir

        #: When
        with pytest.raises(ListSkillsError) as exc_info:
            repository.list_skills(UNIVERSAL_DIR)

        #: Then
        assert f'.agents/{locked.name}' in str(exc_info.value), 'the error names the directory that refused listing'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_list_skills_with_an_unreadable_skill_directory_raises_list_skills_error(
        self, repository: Repository, locked_skill_dir: Path
    ) -> None:
        #: Given
        locked = locked_skill_dir

        #: When
        with pytest.raises(ListSkillsError) as exc_info:
            repository.list_skills(UNIVERSAL_DIR)

        #: Then
        assert f'skills/{locked.name}' in str(exc_info.value), 'the error names the directory that refused listing'
