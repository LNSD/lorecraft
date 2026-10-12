"""The load-failure conditions that stand for an operating system's refusal, each with a trigger and a near miss.

`lorecraft check` reads one snapshot, and a refusal while the snapshot is taken stops the run before any report, so the
rule cases of `test_rule_cases`, which run the command over a repository on disk, cannot trigger these codes. Their
cases are here instead: the model is loaded through a filesystem over the disk, where the refusal happens, and the
run's report of each failure it lists is what is compared. A trigger locks one path so the operating system refuses
it; its near miss is the same tree with nothing locked.
"""

import os
import stat
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Final

import pytest

from lorecraft.engine import report_load_failures
from lorecraft.project.workspace import load_model
from lorecraft.rules.report import LoadFailureReport
from lorecraft.vfs import DiskFileSystem

STRUCTURE_FILE: Final[str] = '{"tokens": 4000}'


@pytest.fixture(scope='function')
def lock() -> Iterator[Callable[[Path], None]]:
    """A function that makes a path refuse every access, restoring each path afterwards for pytest's cleanup.

    Paths are restored in the order they were locked, so a locked parent is searchable again before its child.
    """
    locked: list[tuple[Path, int]] = []

    def lock_path(path: Path) -> None:
        locked.append((path, stat.S_IMODE(path.stat().st_mode)))
        path.chmod(0o000)

    yield lock_path
    for path, mode in locked:
        path.chmod(mode)


def _write(root: Path, relative: str, text: str = '') -> None:
    """Write one file under the root, creating its parents.

    Args:
        root: The repository root.
        relative: Path of the file below `root`.
        text: Content of the file.
    """
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _write_tree(root: Path) -> None:
    """Write a repository with one corpus, one meta spec, and two skills, one of which links its `SKILL.md`.

    Args:
        root: The repository root.
    """
    _write(root, 'docs/__meta__/code.structure.json', STRUCTURE_FILE)
    _write(root, 'docs/code/logging.md', '# Logging\n')
    _write(root, '.agents/skills/commit/SKILL.md', '# Commit\n')
    _write(root, 'texts/REVIEW.md', '# Review\n')
    (root / '.agents' / 'skills' / 'review').mkdir()
    (root / '.agents' / 'skills' / 'review' / 'SKILL.md').symlink_to('../../../texts/REVIEW.md')


def _reported_codes(root: Path) -> list[tuple[str, str]]:
    """The code and path of each load failure the run reports for the repository, in the model's order.

    Args:
        root: The repository root, loaded through a filesystem over the disk.
    """
    model = load_model(DiskFileSystem(root))
    reports: tuple[LoadFailureReport, ...] = report_load_failures(model)
    return [(str(report.occurrence.CODE), str(report.path)) for report in reports]


@pytest.mark.it
@pytest.mark.skipif(os.geteuid() == 0, reason='root ignores file and directory permissions')
class TestLoadFailureConditionsOfARefusal:
    def test_lc002_with_a_structure_file_the_operating_system_refuses_to_read_is_reported_at_the_file(
        self, tmp_path: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        _write_tree(tmp_path)
        lock(tmp_path / 'docs' / '__meta__' / 'code.structure.json')

        #: When
        reported = _reported_codes(tmp_path)

        #: Then
        assert reported == [('LC002', 'docs/__meta__/code.structure.json')], 'the structure file is reported once'

    def test_lc002_with_a_structure_file_that_can_be_read_is_not_reported(self, tmp_path: Path) -> None:
        #: Given
        _write_tree(tmp_path)

        #: When
        reported = _reported_codes(tmp_path)

        #: Then
        assert reported == [], 'a file the check can read is no failure'

    def test_lc014_with_a_corpus_directory_the_operating_system_refuses_to_list_is_reported_at_the_directory(
        self, tmp_path: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        _write_tree(tmp_path)
        lock(tmp_path / 'docs' / 'code')

        #: When
        reported = _reported_codes(tmp_path)

        #: Then
        assert reported == [('LC014', 'docs/code')], 'the corpus directory is reported once, at the directory'

    def test_lc014_with_a_corpus_directory_that_can_be_listed_is_not_reported(self, tmp_path: Path) -> None:
        #: Given
        _write_tree(tmp_path)

        #: When
        reported = _reported_codes(tmp_path)

        #: Then
        assert reported == [], 'a directory the check can list is no failure'

    def test_lc015_with_a_skills_directory_the_operating_system_refuses_to_list_is_reported_at_the_directory(
        self, tmp_path: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        _write_tree(tmp_path)
        lock(tmp_path / '.agents' / 'skills')

        #: When
        reported = _reported_codes(tmp_path)

        #: Then
        assert reported == [('LC015', '.agents/skills')], 'the skills directory is reported once, as declared'

    def test_lc015_with_a_skills_directory_that_can_be_listed_is_not_reported(self, tmp_path: Path) -> None:
        #: Given
        _write_tree(tmp_path)

        #: When
        reported = _reported_codes(tmp_path)

        #: Then
        assert reported == [], 'a skills directory the check can list is no failure'

    def test_lc016_with_a_skill_entry_the_operating_system_refuses_to_list_is_reported_at_the_entry(
        self, tmp_path: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        _write_tree(tmp_path)
        (tmp_path / '.agents' / 'skills' / 'audit').mkdir()
        lock(tmp_path / '.agents' / 'skills' / 'audit')

        #: When
        reported = _reported_codes(tmp_path)

        #: Then
        assert reported == [('LC016', '.agents/skills/audit')], 'the entry is reported once, and the other skills load'

    def test_lc016_with_a_skill_entry_that_can_be_listed_is_not_reported(self, tmp_path: Path) -> None:
        #: Given
        _write_tree(tmp_path)
        (tmp_path / '.agents' / 'skills' / 'audit').mkdir()

        #: When
        reported = _reported_codes(tmp_path)

        #: Then
        assert reported == [], 'an entry the check can list is no failure, even when it holds no SKILL.md'

    def test_lc017_with_a_skill_file_whose_link_the_operating_system_refuses_to_follow_is_reported_at_it(
        self, tmp_path: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        _write_tree(tmp_path)
        lock(tmp_path / 'texts')

        #: When
        reported = _reported_codes(tmp_path)

        #: Then
        assert reported == [('LC017', '.agents/skills/review/SKILL.md')], 'the SKILL.md is reported once, as reached'

    def test_lc017_with_a_skill_file_whose_link_can_be_followed_is_not_reported(self, tmp_path: Path) -> None:
        #: Given
        _write_tree(tmp_path)

        #: When
        reported = _reported_codes(tmp_path)

        #: Then
        assert reported == [], 'a link the check can follow is no failure'
