"""The rules engine's runner over layout entries, in a database opened on a snapshot of a real tree.

A layout entry is a symlink of the skill layout whose chain leaves the repository, as the model's loader and the walk
over a skill's resources find it. The tests hand the runner every entry the run would choose with no path given: the
model's, a skills directory, an entry in one or an entry's `SKILL.md`, then each skill's resource listing's, a symlink
inside that skill. The package's own registry runs `LAY001` over each, which mirrors what `skill.symlink-outside`
reports through the per-check pipeline.
"""

from pathlib import Path, PurePosixPath
from typing import Final

import pytest

from lorecraft import rules
from lorecraft.checks import CheckedLayoutEntry, CheckedSubject, RuleDiagnostic, RuleTable, Subject, check_subjects
from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import Database
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.skill import SkillRef
from lorecraft.rules.declaration import Severity
from lorecraft.rules.layout.outside_symlink import OutsideSymlink
from lorecraft.rules.registry import Registry
from lorecraft.vfs import RootExit, take_snapshot

CLEAN_SKILL_MD: Final[bytes] = b'---\nname: review\ndescription: Review a change\n---\n'
"""A `SKILL.md` the skill `review` passes every other rule with."""


def _write(root: Path, relative: str, data: bytes) -> None:
    """Write one file under the root, creating its parents.

    Args:
        root: Directory the file is written under, as the repository root.
        relative: Path of the file below `root`, with `/` separators.
        data: Bytes written to the file.
    """
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _layout_subjects(database: Database) -> tuple[Subject, ...]:
    """Every layout entry of the snapshot: the model's, then each skill's resource listing's, in the skills' order.

    Args:
        database: Database over the snapshot whose skill layout is checked.
    """
    subjects: list[Subject] = list(database.model().outside_symlinks)
    for location in database.model().skill_locations:
        subjects.extend(database.skill_resources(location).outside_symlinks)
    return tuple(subjects)


def _outside_report(path: str, link: str, target: Path | str) -> CheckedLayoutEntry:
    """The report of the layout entry at `path`, whose chain leaves the repository at `link -> target`.

    Args:
        path: Where an agent reaches the symlink, root-relative.
        link: The link the chain leaves the repository through, root-relative.
        target: That link's target, as the scan read it.
    """
    entry = RootRelativePath.parse(path)
    occurrence = OutsideSymlink(leaves_at=RootExit(RootRelativePath.parse(link), PurePosixPath(target)))
    return CheckedLayoutEntry(entry, diagnostics=(RuleDiagnostic(entry, occurrence, Severity.ERROR),))


@pytest.fixture(scope='module')
def package_table() -> RuleTable:
    """The rule table of the package's own rules at their default levels; immutable, so shared by the module."""
    return RuleTable.from_registry(Registry.load(rules))


@pytest.fixture(scope='function')
def repository_beside_elsewhere(tmp_path: Path) -> Path:
    """An empty repository root, `tmp_path/repository`, beside `tmp_path/elsewhere`, a directory outside it.

    `elsewhere` holds a conforming skill, `x`, and a Markdown file, `x.md`, for a link to lead to.

    Args:
        tmp_path: Directory the repository and the directory outside it are written into.

    Returns:
        The repository root.
    """
    _write(tmp_path, 'elsewhere/x/SKILL.md', b'---\nname: x\ndescription: Kept outside\n---\n')
    _write(tmp_path, 'elsewhere/x.md', CLEAN_SKILL_MD)
    root = tmp_path / 'repository'
    root.mkdir()
    return root


@pytest.mark.it
class TestCheckSubjectsLayout:
    def test_check_subjects_with_a_skills_directory_linked_outside_reports_it_at_the_skills_directory(
        self, repository_beside_elsewhere: Path, package_table: RuleTable
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        elsewhere = root.parent / 'elsewhere'
        (root / '.claude').mkdir()
        (root / '.claude' / 'skills').symlink_to(elsewhere)
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        reports = check_subjects(database, _layout_subjects(database), package_table)

        #: Then
        assert reports == (_outside_report('.claude/skills', '.claude/skills', elsewhere),), (
            'an agent would load its skills from outside the repository, so the skills directory is reported'
        )

    def test_check_subjects_with_a_skill_entry_linked_outside_reports_it_at_the_entry(
        self, repository_beside_elsewhere: Path, package_table: RuleTable
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        target = root.parent / 'elsewhere' / 'x'
        (root / '.agents' / 'skills').mkdir(parents=True)
        (root / '.agents' / 'skills' / 'x').symlink_to(target)
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        reports = check_subjects(database, _layout_subjects(database), package_table)

        #: Then
        assert reports == (_outside_report('.agents/skills/x', '.agents/skills/x', target),), (
            'the entry an agent lists is reported where it is listed'
        )

    def test_check_subjects_with_a_skill_file_linked_outside_reports_it_at_the_skill_file(
        self, repository_beside_elsewhere: Path, package_table: RuleTable
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        target = root.parent / 'elsewhere' / 'x.md'
        (root / '.agents' / 'skills' / 'review').mkdir(parents=True)
        (root / '.agents' / 'skills' / 'review' / 'SKILL.md').symlink_to(target)
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        reports = check_subjects(database, _layout_subjects(database), package_table)

        #: Then
        assert reports == (
            _outside_report('.agents/skills/review/SKILL.md', '.agents/skills/review/SKILL.md', target),
        ), 'the SKILL.md an agent would read from outside the repository is reported where the agent reaches it'

    def test_check_subjects_with_a_directory_inside_a_skill_linked_outside_reports_it_where_the_agent_reaches_it(
        self, repository_beside_elsewhere: Path, package_table: RuleTable
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        target = root.parent / 'elsewhere' / 'x'
        _write(root, '.agents/skills/review/SKILL.md', CLEAN_SKILL_MD)
        (root / '.agents' / 'skills' / 'review' / 'references').symlink_to(target)
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        reports = check_subjects(database, _layout_subjects(database), package_table)

        #: Then
        assert reports == (
            _outside_report('.agents/skills/review/references', '.agents/skills/review/references', target),
        ), 'a directory of the skill linked outside is reported under the skill an agent lists'

    def test_check_subjects_with_a_chain_inside_the_repository_that_leaves_it_reports_the_link_it_leaves_through(
        self, repository_beside_elsewhere: Path, package_table: RuleTable
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        elsewhere = root.parent / 'elsewhere'
        (root / '.agents' / 'skills').mkdir(parents=True)
        (root / '.agents' / 'skills' / 'x').symlink_to('../../hop/x')
        (root / 'hop').symlink_to(elsewhere)
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        reports = check_subjects(database, _layout_subjects(database), package_table)

        #: Then
        assert reports == (_outside_report('.agents/skills/x', 'hop', elsewhere),), (
            'the entry an agent lists is reported, and its note names the link the chain leaves through'
        )

    def test_check_subjects_with_a_link_climbing_above_the_repository_reports_it(
        self, repository_beside_elsewhere: Path, package_table: RuleTable
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        _write(root, '.agents/skills/review/SKILL.md', CLEAN_SKILL_MD)
        (root / '.agents' / 'skills' / 'review' / 'shared').symlink_to('../../../../elsewhere/x')
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        reports = check_subjects(database, _layout_subjects(database), package_table)

        #: Then
        assert reports == (
            _outside_report('.agents/skills/review/shared', '.agents/skills/review/shared', '../../../../elsewhere/x'),
        ), 'a `..` climbing above the root leaves the repository as an absolute target does'

    def test_check_subjects_with_a_link_dangling_inside_the_repository_finds_no_layout_entry(
        self, repository_beside_elsewhere: Path, package_table: RuleTable
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        _write(root, '.agents/skills/review/SKILL.md', CLEAN_SKILL_MD)
        (root / '.agents' / 'skills' / 'gone').symlink_to('../../skills/gone')
        (root / '.agents' / 'skills' / 'review' / 'references').symlink_to('../../../missing')
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        reports = check_subjects(database, _layout_subjects(database), package_table)

        #: Then
        assert reports == (), 'a link dangling inside the repository is not one leading outside it, so none is judged'

    def test_check_subjects_with_a_skills_directory_linked_inside_the_repository_finds_no_layout_entry(
        self, repository_beside_elsewhere: Path, package_table: RuleTable
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        _write(root, '.agents/skills/review/SKILL.md', CLEAN_SKILL_MD)
        (root / '.claude').mkdir()
        (root / '.claude' / 'skills').symlink_to('../.agents/skills')
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        reports = check_subjects(database, _layout_subjects(database), package_table)

        #: Then
        assert reports == (), 'a skills directory linked to another inside the repository is self-contained'

    def test_check_subjects_with_a_skill_and_its_layout_entry_reports_them_in_the_order_given(
        self, repository_beside_elsewhere: Path, package_table: RuleTable
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        target = root.parent / 'elsewhere' / 'x'
        _write(root, '.agents/skills/review/SKILL.md', CLEAN_SKILL_MD)
        (root / '.agents' / 'skills' / 'review' / 'references').symlink_to(target)
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))
        location = database.model().find_skill_location(RootRelativePath.parse('.agents/skills/review'))
        assert location is not None, 'the model lists the skill .agents/skills/review'
        subjects: tuple[Subject, ...] = (*_layout_subjects(database), location)

        #: When
        reports = check_subjects(database, subjects, package_table)

        #: Then
        assert reports == (
            _outside_report('.agents/skills/review/references', '.agents/skills/review/references', target),
            CheckedSubject(SkillRef(RootRelativePath.parse('.agents/skills/review')), diagnostics=(), ungoverned=()),
        ), 'a layout entry and a skill share one run, each reported in the order given'
