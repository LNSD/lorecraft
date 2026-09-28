"""Skill repository behavior against a real skills tree.

The repository is wired to a real ``DiskFileSystem`` over ``tmp_path``, so entry kinds come from ``os.scandir``,
link chains are followed by ``os.path.realpath``, and the error families come from the operating system
refusing a lookup. Links are written relative, the way the target repositories write them.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from lorecraft_project.skill.repo import (
    ListSkillEntriesError,
    ProbeSkillMdError,
    Repository,
    ResolveSkillDirectoryError,
    SkillEntry,
)
from lorecraft_vfs import DiskFileSystem, EntryKind, ListDirError, ResolveDirError, RootRelativePath


@pytest.fixture(scope='function')
def repository(tmp_path: Path) -> Repository:
    """A repository over the temporary root; no skills directory exists until a test creates it."""
    return Repository(DiskFileSystem(tmp_path))


@pytest.fixture(scope='function')
def skills_dir(tmp_path: Path) -> Path:
    """An empty canonical ``.agents/skills/`` directory under the temporary root."""
    directory = tmp_path / '.agents' / 'skills'
    directory.mkdir(parents=True)
    return directory


@pytest.fixture(scope='function')
def locked_skills_dir(skills_dir: Path) -> Iterator[Path]:
    """A ``.agents/skills/`` whose permissions refuse listing, restored afterwards so pytest can clean it up."""
    skills_dir.chmod(0o000)
    yield skills_dir
    skills_dir.chmod(0o700)


@pytest.fixture(scope='function')
def locked_skill_dir(skills_dir: Path) -> Iterator[Path]:
    """A ``.agents/skills/deploy/`` whose permissions refuse listing, restored afterwards for cleanup."""
    directory = skills_dir / 'deploy'
    directory.mkdir()
    (directory / 'SKILL.md').write_text('', encoding='utf-8')
    directory.chmod(0o000)
    yield directory
    directory.chmod(0o700)


@pytest.mark.it
class TestRepositoryListEntries:
    def test_list_entries_with_directories_links_and_files_returns_only_directories_and_links_sorted(
        self, skills_dir: Path, repository: Repository
    ) -> None:
        #: Given
        (skills_dir / 'review').mkdir()
        (skills_dir / 'deploy').mkdir()
        (skills_dir / 'linked').symlink_to('review')
        (skills_dir / 'README.md').write_text('', encoding='utf-8')
        skills = RootRelativePath.parse('.agents/skills')

        #: When
        entries = repository.list_entries(skills)

        #: Then
        assert entries == (
            SkillEntry(skills / 'deploy', 'deploy', EntryKind.DIRECTORY),
            SkillEntry(skills / 'linked', 'linked', EntryKind.SYMLINK),
            SkillEntry(skills / 'review', 'review', EntryKind.DIRECTORY),
        ), 'directories and links are listed by name with their unresolved path, and a file is dropped'

    def test_list_entries_with_a_missing_directory_returns_empty(self, repository: Repository) -> None:
        #: Given
        missing = RootRelativePath.parse('.agents/skills')

        #: When
        entries = repository.list_entries(missing)

        #: Then
        assert entries == (), 'a missing skills directory lists as nothing rather than failing'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_list_entries_with_an_unreadable_directory_raises_list_skill_entries_error(
        self, locked_skills_dir: Path, repository: Repository
    ) -> None:
        #: Given
        locked = RootRelativePath.parse('.agents/skills')

        #: When
        with pytest.raises(ListSkillEntriesError) as exc_info:
            repository.list_entries(locked)

        #: Then
        assert exc_info.value.path == locked, 'the error names the root-relative skills directory'
        assert isinstance(exc_info.value.__cause__, ListDirError), 'the seam error is chained as the cause'


@pytest.mark.it
class TestRepositoryResolveDirectory:
    def test_resolve_directory_with_a_relative_link_returns_the_target(
        self, tmp_path: Path, skills_dir: Path, repository: Repository
    ) -> None:
        #: Given
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')

        #: When
        resolved = repository.resolve_directory(RootRelativePath.parse('.claude/skills'))

        #: Then
        assert resolved == RootRelativePath.parse('.agents/skills'), 'a relative link resolves to the real directory'

    def test_resolve_directory_with_a_dangling_link_returns_none(self, tmp_path: Path, repository: Repository) -> None:
        #: Given
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('missing')

        #: When
        resolved = repository.resolve_directory(RootRelativePath.parse('.claude/skills'))

        #: Then
        assert resolved is None, 'a link that leads to no directory under the root resolves to nothing'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_resolve_directory_under_an_unreadable_directory_raises_resolve_skill_directory_error(
        self, locked_skills_dir: Path, repository: Repository
    ) -> None:
        #: Given
        inside_locked = RootRelativePath.parse('.agents/skills/deploy')

        #: When
        with pytest.raises(ResolveSkillDirectoryError) as exc_info:
            repository.resolve_directory(inside_locked)

        #: Then
        assert exc_info.value.path == inside_locked, 'the error names the root-relative path'
        assert isinstance(exc_info.value.__cause__, ResolveDirError), 'the seam error is chained as the cause'


@pytest.mark.it
class TestRepositoryHasSkillMd:
    def test_has_skill_md_with_a_regular_file_returns_true(self, skills_dir: Path, repository: Repository) -> None:
        #: Given
        (skills_dir / 'deploy').mkdir()
        (skills_dir / 'deploy' / 'SKILL.md').write_text('', encoding='utf-8')

        #: When
        found = repository.has_skill_md(RootRelativePath.parse('.agents/skills/deploy'))

        #: Then
        assert found is True, 'a regular SKILL.md file marks the directory as a skill'

    def test_has_skill_md_with_a_symlinked_file_returns_false(self, skills_dir: Path, repository: Repository) -> None:
        #: Given
        (skills_dir / 'deploy').mkdir()
        (skills_dir / 'deploy' / 'notes.md').write_text('', encoding='utf-8')
        (skills_dir / 'deploy' / 'SKILL.md').symlink_to('notes.md')

        #: When
        found = repository.has_skill_md(RootRelativePath.parse('.agents/skills/deploy'))

        #: Then
        assert found is False, 'a symlink named SKILL.md does not count, as in vercel hasSkillMd().isFile()'

    def test_has_skill_md_with_a_directory_of_that_name_returns_false(
        self, skills_dir: Path, repository: Repository
    ) -> None:
        #: Given
        (skills_dir / 'deploy' / 'SKILL.md').mkdir(parents=True)

        #: When
        found = repository.has_skill_md(RootRelativePath.parse('.agents/skills/deploy'))

        #: Then
        assert found is False, 'a directory named SKILL.md does not count'

    def test_has_skill_md_with_a_missing_directory_returns_false(self, repository: Repository) -> None:
        #: Given
        missing = RootRelativePath.parse('.agents/skills/deploy')

        #: When
        found = repository.has_skill_md(missing)

        #: Then
        assert found is False, 'a missing directory holds no SKILL.md rather than failing'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
    def test_has_skill_md_with_an_unreadable_directory_raises_probe_skill_md_error(
        self, locked_skill_dir: Path, repository: Repository
    ) -> None:
        #: Given
        locked = RootRelativePath.parse('.agents/skills/deploy')

        #: When
        with pytest.raises(ProbeSkillMdError) as exc_info:
            repository.has_skill_md(locked)

        #: Then
        assert exc_info.value.path == locked, 'the error names the root-relative skill directory'
        assert isinstance(exc_info.value.__cause__, ListDirError), 'the seam error is chained as the cause'
