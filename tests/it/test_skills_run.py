"""The skill run over a database opened on a snapshot of a real tree.

``run_skills`` reads everything through the database, and the database answers from one snapshot, so the run
reports the skills as the scan saw them, through whichever link an agent reaches each by.
"""

from pathlib import Path

import pytest

from lorecraft.checks import Database, SkillCheckRun, Violation, run_skills
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.syntax import LineNumber
from lorecraft.vfs import take_snapshot


def _write(root: Path, relative: str, data: bytes = b'') -> Path:
    """Write one file under the root, creating its parents, and return its path."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _run_every_skill(database: Database) -> SkillCheckRun:
    """Check every skill the database's model lists."""
    return run_skills(database, database.model().skills())


@pytest.fixture(scope='function')
def skills_tree(tmp_path: Path) -> Path:
    """A root whose skills produce every kind of report.

    Under ``.agents/skills/``: ``clean`` conforms; ``misnamed`` names another skill; ``undescribed`` has no
    description; ``bare`` has no frontmatter; ``latin`` is not UTF-8; ``extended`` uses a field outside the
    specification; and ``shipped`` is a link to ``skills/shipped/``, outside the skills directories, which
    conforms.
    """
    skills = '.agents/skills'
    _write(tmp_path, f'{skills}/clean/SKILL.md', b'---\nname: clean\ndescription: A clean skill\n---\n')
    _write(tmp_path, f'{skills}/misnamed/SKILL.md', b'---\nname: other\ndescription: Named wrong\n---\n')
    _write(tmp_path, f'{skills}/undescribed/SKILL.md', b'---\nname: undescribed\n---\n')
    _write(tmp_path, f'{skills}/bare/SKILL.md', b'# No frontmatter\n')
    _write(tmp_path, f'{skills}/latin/SKILL.md', b'---\nname: caf\xe9\n---\n')
    _write(tmp_path, f'{skills}/extended/SKILL.md', b'---\nname: extended\ndescription: Extended\nmodel: opus\n---\n')
    _write(tmp_path, 'skills/shipped/SKILL.md', b'---\nname: shipped\ndescription: Shipped from skills/\n---\n')
    (tmp_path / '.agents' / 'skills' / 'shipped').symlink_to('../../skills/shipped')
    return tmp_path


@pytest.mark.it
class TestRunSkills:
    def test_run_skills_over_a_snapshot_reports_one_rule_per_broken_skill(self, skills_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skills_tree, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        rules = [(str(finding.path), finding.line.value, finding.rule) for finding in run.findings()]
        assert rules == [
            ('.agents/skills/bare/SKILL.md', 1, 'skill.frontmatter-missing'),
            ('.agents/skills/extended/SKILL.md', 4, 'skill.unknown-field'),
            ('.agents/skills/latin/SKILL.md', 1, 'skill.undecodable'),
            ('.agents/skills/misnamed/SKILL.md', 2, 'skill.name-matches-directory'),
            ('.agents/skills/undescribed/SKILL.md', 1, 'skill.description'),
        ], 'each broken skill yields exactly the finding its defect names, in the order the model lists them'

    def test_run_skills_over_a_snapshot_reports_every_skill_it_was_handed(self, skills_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skills_tree, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [str(report.ref.directory) for report in run.reports] == [
            '.agents/skills/bare',
            '.agents/skills/clean',
            '.agents/skills/extended',
            '.agents/skills/latin',
            '.agents/skills/misnamed',
            '.agents/skills/shipped',
            '.agents/skills/undescribed',
        ], 'one report per skill, clean ones included, the linked skill among them'

    def test_run_skills_over_a_snapshot_reads_a_skill_linked_outside_the_skills_directories(
        self, skills_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(skills_tree, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        shipped = [report for report in run.reports if report.ref.directory.name == 'shipped']
        assert [report.violations for report in shipped] == [()], (
            'the linked skill is read through its link and found clean, not reported as unreadable'
        )

    def test_run_skills_after_the_disk_changes_reports_the_skills_the_snapshot_saw(self, skills_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skills_tree, SNAPSHOT_SCOPE))
        _write(
            skills_tree, '.agents/skills/bare/SKILL.md', b'---\nname: bare\ndescription: Fixed after the scan\n---\n'
        )

        #: When
        run = _run_every_skill(database)

        #: Then
        bare = [finding.rule for finding in run.findings() if finding.path.parent.name == 'bare']
        assert bare == ['skill.frontmatter-missing'], 'the run reads the snapshot, not the disk as it is now'

    def test_run_skills_with_the_wrong_name_written_last_reports_it_and_the_repetition_on_that_line(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            b'---\nname: review\ndescription: Review a change\nname: audit\n---\n',
        )
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [report.violations for report in run.reports] == [
            (
                Violation(
                    line=LineNumber(4),
                    rule='skill.name-matches-directory',
                    message="`name` is 'audit'; expected 'review', the name of the skill directory",
                ),
                Violation(
                    line=LineNumber(4),
                    rule='skill.duplicate-key',
                    message="'name' is already written on line 2",
                ),
            )
        ], 'the name the decoder kept is judged on the last line it is written on, beside the repetition'

    def test_run_skills_with_the_right_name_written_last_reports_only_the_repetition(self, tmp_path: Path) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            b'---\nname: audit\ndescription: Review a change\nname: review\n---\n',
        )
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [report.violations for report in run.reports] == [
            (
                Violation(
                    line=LineNumber(4),
                    rule='skill.duplicate-key',
                    message="'name' is already written on line 2",
                ),
            )
        ], 'the decoder kept the right name, so the overwritten wrong one is reported only as a repetition'
