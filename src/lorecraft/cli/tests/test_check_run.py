"""The check registry a bare ``lorecraft check`` reads: what a check module's registration may and may not do;
then the selection's refusal of an unreadable working directory, and the summary of a bare run with no checks.

The registry is process-wide, so these cases register only the frontmatter check itself, or a rival under its name
that is refused before it is stored; a new name would join every later bare run in the same process.
"""

from pathlib import Path

import pytest

from lorecraft.checks import Database, SkillCheckRun, run_frontmatter, run_skills
from lorecraft.project.skill import SkillRef
from lorecraft.vfs import OsRefusal

from ..check_run import (
    DocumentCheck,
    DuplicateCheckError,
    SkillCheck,
    WorkingDirectoryReadError,
    print_runs,
    register_check,
    register_skill_check,
    registered_checks,
    registered_skill_checks,
    select_documents,
)
from ..commands.check.frontmatter import FRONTMATTER_CHECK
from ..commands.check.skills import SKILLS_CHECK


def _rival_skill_run(database: Database, refs: tuple[SkillRef, ...]) -> SkillCheckRun:
    """Stand-in run for a rival skill check that must be refused before it is ever run."""
    raise AssertionError('a refused check is never run')


@pytest.mark.unit
class TestRegisterCheck:
    def test_register_check_with_the_same_check_again_keeps_one_entry(self) -> None:
        #: Given
        before = registered_checks()

        #: When
        returned = register_check(FRONTMATTER_CHECK)

        #: Then
        assert returned is FRONTMATTER_CHECK, 'registration returns the check unchanged, so it can be bound to a name'
        assert registered_checks() == before, 'registering the same check twice is a no-op'

    def test_register_check_with_a_different_check_under_a_taken_name_raises_duplicate_check_error(self) -> None:
        #: Given
        rival = DocumentCheck(name=FRONTMATTER_CHECK.name, run=run_frontmatter, ungoverned='another message')

        #: When
        with pytest.raises(DuplicateCheckError) as exc_info:
            register_check(rival)

        #: Then
        assert exc_info.value.name == FRONTMATTER_CHECK.name, 'the error names the contested check'

    def test_register_check_under_the_name_of_a_skill_check_raises_duplicate_check_error(self) -> None:
        #: Given
        rival = DocumentCheck(name=SKILLS_CHECK.name, run=run_frontmatter, ungoverned='another message')

        #: When
        with pytest.raises(DuplicateCheckError) as exc_info:
            register_check(rival)

        #: Then
        assert exc_info.value.name == SKILLS_CHECK.name, 'a document check cannot take the name of a skill check'


@pytest.mark.unit
class TestRegisterSkillCheck:
    def test_register_skill_check_with_the_same_check_again_keeps_one_entry(self) -> None:
        #: Given
        before = registered_skill_checks()

        #: When
        returned = register_skill_check(SKILLS_CHECK)

        #: Then
        assert returned is SKILLS_CHECK, 'registration returns the check unchanged, so it can be bound to a name'
        assert registered_skill_checks() == before, 'registering the same check twice is a no-op'

    def test_register_skill_check_with_a_different_check_under_a_taken_name_raises_duplicate_check_error(
        self,
    ) -> None:
        #: Given
        rival = SkillCheck(name=SKILLS_CHECK.name, run=_rival_skill_run)

        #: When
        with pytest.raises(DuplicateCheckError) as exc_info:
            register_skill_check(rival)

        #: Then
        assert exc_info.value.name == SKILLS_CHECK.name, 'the error names the contested check'

    def test_register_skill_check_under_the_name_of_a_document_check_raises_duplicate_check_error(self) -> None:
        #: Given
        rival = SkillCheck(name=FRONTMATTER_CHECK.name, run=run_skills)

        #: When
        with pytest.raises(DuplicateCheckError) as exc_info:
            register_skill_check(rival)

        #: Then
        assert exc_info.value.name == FRONTMATTER_CHECK.name, (
            'a skill check cannot take the name of a document check: the bare report keys both by name'
        )


@pytest.mark.unit
class TestRegisteredChecks:
    def test_registered_checks_with_the_header_alias_declared_holds_the_frontmatter_check_once(self) -> None:
        #: Given
        alias = 'header'

        #: When
        names = [check.name for check in registered_checks()]

        #: Then
        assert names.count(FRONTMATTER_CHECK.name) == 1, 'the frontmatter check is registered once'
        assert alias not in names, 'the alias is a second command name, not a second check a bare run would repeat'


@pytest.mark.unit
class TestSelectDocuments:
    def test_select_documents_without_a_root_from_a_deleted_working_directory_raises_working_directory_read_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        deleted = tmp_path / 'deleted'
        deleted.mkdir()
        monkeypatch.chdir(deleted)
        deleted.rmdir()

        #: When
        with pytest.raises(WorkingDirectoryReadError) as exc_info:
            select_documents(None, None)

        #: Then
        assert exc_info.value.refusal is OsRefusal.NOT_FOUND, 'a deleted working directory is refused as not found'
        assert isinstance(exc_info.value.source, FileNotFoundError), 'the operating system failure is kept'


@pytest.mark.unit
class TestPrintRuns:
    def test_print_runs_with_no_runs_prints_a_summary_of_nothing_checked(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        runs = ()

        #: When
        print_runs(runs, (), 'text')

        #: Then
        captured = capsys.readouterr()
        assert captured.out == '', 'no run prints no line'
        assert captured.err == 'checked 0 file(s) and 0 skill(s) with 0 check(s), 0 finding(s)\n', (
            'with no run there is no file, skill, check or finding to count'
        )
