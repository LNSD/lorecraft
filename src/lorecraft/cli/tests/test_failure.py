"""Reporting a failure a command cannot recover from: the error, then the errors beneath it."""

import re

import pytest
import typer
from jsonschema.exceptions import SchemaError
from pydantic import ValidationError

from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document.repo import CorpusListError
from lorecraft.project.schemas.name import CorpusSpecName
from lorecraft.project.schemas.repo import StructureSchemaReadError
from lorecraft.project.schemas.section_name import SectionName
from lorecraft.project.schemas.structure import (
    AdjacentAnyRunsError,
    EmptyStructureSpecError,
    ForbiddenOutlineSectionError,
    ForeignFrontmatterDialectError,
    FrontmatterSchemaIdError,
    InvalidFrontmatterSchemaError,
    InvalidTitlePatternError,
    RepeatedForbiddenSectionError,
    RepeatedOutlineSectionError,
    StructureSpecDecodeError,
    UntypedFrontmatterSchemaError,
)
from lorecraft.project.skill import (
    SkillDirListError,
    SkillEntryResolveError,
    SkillFileResolveError,
    SkillsDirListError,
)
from lorecraft.project.workspace import (
    AdjacentAnyRuns,
    EmptyStructureSpec,
    ForbiddenOutlineSections,
    ForeignFrontmatterDialect,
    FrontmatterSchemaId,
    InvalidFrontmatterSchema,
    InvalidTitlePattern,
    LoadFailure,
    NonUtf8StructureFile,
    RepeatedForbiddenSections,
    RepeatedOutlineSections,
    UndecodableStructureSpec,
    UninspectableSkillEntry,
    UninspectableSkillFile,
    UninspectableSkillsDirectory,
    UnlistableCorpusDirectory,
    UnlistableDirectory,
    UnlistableSkillDirectory,
    UnlistableSkillsDirectory,
    UnreadableStructureFile,
    UnrecordedStructureFile,
    UnresolvableSkillEntry,
    UnresolvableSkillFile,
    UnresolvableSkillsDirectory,
    UntypedFrontmatterSchema,
    WorkspaceModel,
)
from lorecraft.vfs import (
    DirListError,
    DirResolveError,
    EntryInspectError,
    FileReadError,
    FileResolveError,
    OsRefusal,
    TextDecodeError,
    UnrecordedFileError,
    Utf8Failure,
)

from ..failure import exit_on_load_failure, exit_on_unlistable_directory, report_failure, report_load_failure
from ..output import ExitStatus


@pytest.mark.unit
class TestReportFailure:
    def test_report_failure_without_a_cause_writes_one_error_line(self, capsys: pytest.CaptureFixture[str]) -> None:
        #: Given
        failure = Error('cannot find repository root')

        #: When
        report_failure(failure)

        #: Then
        captured = capsys.readouterr()
        assert captured.err == 'error: cannot find repository root\n', 'a failure with no cause is one line'
        assert captured.out == '', 'nothing is written to stdout'

    def test_report_failure_with_errors_beneath_writes_a_line_per_cause(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        read = Error('cannot read specification docs/__meta__/code.json')
        read.__cause__ = PermissionError(13, 'Permission denied')
        load = Error('cannot load the outline of corpus code')
        load.__cause__ = read

        #: When
        report_failure(load)

        #: Then
        assert capsys.readouterr().err == (
            'error: cannot load the outline of corpus code\n'
            '  caused by: cannot read specification docs/__meta__/code.json\n'
        ), 'each error on the chain is a line, and the foreign exception beneath them is not'

    def test_report_failure_with_two_errors_beneath_writes_a_line_for_each(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        parse = Error('docs/__meta__/code.json is not JSON')
        read = Error('cannot read specification docs/__meta__/code.json')
        read.__cause__ = parse
        load = Error('cannot load the outline of corpus code')
        load.__cause__ = read

        #: When
        report_failure(load)

        #: Then
        assert capsys.readouterr().err == (
            'error: cannot load the outline of corpus code\n'
            '  caused by: cannot read specification docs/__meta__/code.json\n'
            '  caused by: docs/__meta__/code.json is not JSON\n'
        ), 'the walk follows the chain past the first cause, down to the last error'


_PATH = RootRelativePath.parse('docs/__meta__/code.structure.json')
_DOCS = RootRelativePath.parse('docs')
_CORPUS = CorpusName.parse('code')
_CORPUS_DIR = RootRelativePath.parse('docs/code')
_SPEC_NAME = CorpusSpecName(_CORPUS)
_SKILLS_DIR = RootRelativePath.parse('.claude/skills')
# The directory, entry and file a link in the skills layout leads to, as the repository's errors name them.
_TARGET_DIR = RootRelativePath.parse('shared/skills')
_ENTRY = RootRelativePath.parse('.claude/skills/review')
_ENTRY_FILE = RootRelativePath.parse('.claude/skills/review/SKILL.md')
_TARGET_FILE = RootRelativePath.parse('shared/review/SKILL.md')
_INNER = RootRelativePath.parse('shared/review/inner')
_PROBLEMS = ('outline: Field required', 'tokens: not a number')
_REFUSAL = OsRefusal.PERMISSION_DENIED
_OS_ERROR = OSError()


def _written_for(capsys: pytest.CaptureFixture[str], failure: LoadFailure, error: Error) -> tuple[str, str]:
    """What `report_failure` wrote for the replaced error, and what `report_load_failure` wrote for the failure.

    Args:
        capsys: Captures what each report writes to stderr.
        failure: The recorded failure.
        error: The error the loader raised for it before failures were recorded.

    Returns:
        The report of the error, then the report of the recorded failure.
    """
    report_failure(error)
    expected = capsys.readouterr().err

    report_load_failure(failure)
    return expected, capsys.readouterr().err


@pytest.mark.unit
class TestReportLoadFailure:
    def test_report_load_failure_with_unreadable_structure_file_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, UnreadableStructureFile(_SPEC_NAME, _REFUSAL))
        error = StructureSchemaReadError(_SPEC_NAME, source=FileReadError(_PATH, _REFUSAL, source=_OS_ERROR))

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_unrecorded_structure_file_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, UnrecordedStructureFile(_SPEC_NAME))
        error = StructureSchemaReadError(_SPEC_NAME, source=UnrecordedFileError(_PATH))

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_non_utf8_structure_file_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        decode_error = UnicodeDecodeError('utf-8', b'\xe9', 0, 1, 'invalid continuation byte')
        failure = LoadFailure(_PATH, NonUtf8StructureFile(Utf8Failure.from_error(decode_error)))
        error = TextDecodeError(_PATH, source=decode_error)

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_undecodable_structure_spec_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, UndecodableStructureSpec(_PROBLEMS))
        error = StructureSpecDecodeError(
            _PATH, _PROBLEMS, source=ValidationError.from_exception_data('StructureFile', [])
        )

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_empty_structure_spec_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, EmptyStructureSpec())
        error = EmptyStructureSpecError(_PATH)

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_repeated_outline_sections_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, RepeatedOutlineSections((SectionName('Usage'),)))
        error = RepeatedOutlineSectionError(_PATH, (SectionName('Usage'),))

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_repeated_forbidden_sections_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, RepeatedForbiddenSections((SectionName('Changelog'),)))
        error = RepeatedForbiddenSectionError(_PATH, (SectionName('Changelog'),))

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_forbidden_outline_sections_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, ForbiddenOutlineSections((SectionName('Usage'),)))
        error = ForbiddenOutlineSectionError(_PATH, (SectionName('Usage'),))

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_adjacent_any_runs_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, AdjacentAnyRuns())
        error = AdjacentAnyRunsError(_PATH)

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_invalid_title_pattern_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, InvalidTitlePattern('(', 'missing )'))
        error = InvalidTitlePatternError(_PATH, '(', 'missing )', source=re.error('missing )'))

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_invalid_frontmatter_schema_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, InvalidFrontmatterSchema('5 is not valid'))
        error = InvalidFrontmatterSchemaError(_PATH, '5 is not valid', source=SchemaError('5 is not valid'))

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_frontmatter_schema_id_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, FrontmatterSchemaId())
        error = FrontmatterSchemaIdError(_PATH)

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_foreign_frontmatter_dialect_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, ForeignFrontmatterDialect("'draft-07'"))
        error = ForeignFrontmatterDialectError(_PATH, 'draft-07')

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_untyped_frontmatter_schema_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, UntypedFrontmatterSchema())
        error = UntypedFrontmatterSchemaError(_PATH)

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_unlistable_directory_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_DOCS, UnlistableDirectory(_REFUSAL))
        error = DirListError(_DOCS, _REFUSAL, source=_OS_ERROR)

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_unlistable_corpus_directory_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_CORPUS_DIR, UnlistableCorpusDirectory(_CORPUS, _REFUSAL))
        error = CorpusListError(_CORPUS, source=DirListError(_CORPUS_DIR, _REFUSAL, source=_OS_ERROR))

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_unresolvable_skills_directory_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_SKILLS_DIR, UnresolvableSkillsDirectory(_REFUSAL))
        error = DirResolveError(_SKILLS_DIR, _REFUSAL, source=_OS_ERROR)

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_uninspectable_skills_directory_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_SKILLS_DIR, UninspectableSkillsDirectory(_INNER, _REFUSAL))
        error = EntryInspectError(_INNER, _REFUSAL, source=_OS_ERROR)

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_unlistable_skills_directory_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_SKILLS_DIR, UnlistableSkillsDirectory(_TARGET_DIR, _REFUSAL))
        error = SkillsDirListError(_TARGET_DIR, source=DirListError(_TARGET_DIR, _REFUSAL, source=_OS_ERROR))

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_unresolvable_skill_entry_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_ENTRY, UnresolvableSkillEntry(_REFUSAL))
        error = SkillEntryResolveError(_ENTRY, source=DirResolveError(_ENTRY, _REFUSAL, source=_OS_ERROR))

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_uninspectable_skill_entry_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_ENTRY, UninspectableSkillEntry(_INNER, _REFUSAL))
        error = SkillEntryResolveError(_ENTRY, source=EntryInspectError(_INNER, _REFUSAL, source=_OS_ERROR))

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_unlistable_skill_directory_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_ENTRY, UnlistableSkillDirectory(_TARGET_DIR, _REFUSAL))
        error = SkillDirListError(_TARGET_DIR, source=DirListError(_TARGET_DIR, _REFUSAL, source=_OS_ERROR))

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_unresolvable_skill_file_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_ENTRY_FILE, UnresolvableSkillFile(_TARGET_FILE, _REFUSAL))
        error = SkillFileResolveError(_TARGET_FILE, source=FileResolveError(_TARGET_FILE, _REFUSAL, source=_OS_ERROR))

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'

    def test_report_load_failure_with_uninspectable_skill_file_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_ENTRY_FILE, UninspectableSkillFile(_TARGET_FILE, _INNER, _REFUSAL))
        error = SkillFileResolveError(_TARGET_FILE, source=EntryInspectError(_INNER, _REFUSAL, source=_OS_ERROR))

        #: When
        expected, actual = _written_for(capsys, failure, error)

        #: Then
        assert actual == expected, 'the interim report is the one the raised error gave'


@pytest.mark.unit
class TestExitOnLoadFailure:
    def test_exit_on_load_failure_with_no_failure_returns(self) -> None:
        #: Given
        model = WorkspaceModel(corpora=(), skills_dirs=(), skill_locations=(), outside_symlinks=(), load_failures=())

        #: When
        exit_on_load_failure(model)

        #: Then
        # reaching here is the assertion: a model that recorded nothing is no reason to stop

    def test_exit_on_load_failure_with_failures_reports_the_first_and_exits_two(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        first = LoadFailure(RootRelativePath.parse('docs/__meta__'), UnlistableDirectory(_REFUSAL))
        second = LoadFailure(RootRelativePath.parse('docs'), UnlistableDirectory(_REFUSAL))
        model = WorkspaceModel(
            corpora=(), skills_dirs=(), skill_locations=(), outside_symlinks=(), load_failures=(first, second)
        )

        #: When
        with pytest.raises(typer.Exit) as exc_info:
            exit_on_load_failure(model)

        #: Then
        assert exc_info.value.exit_code == ExitStatus.FAILURE, 'the run exits as an error did'
        assert capsys.readouterr().err == 'error: cannot list directory docs/__meta__: permission denied\n', (
            'only the first failure is reported, as only the first error was raised'
        )


@pytest.mark.unit
class TestExitOnUnlistableDirectory:
    def test_exit_on_unlistable_directory_with_no_failure_returns(self, capsys: pytest.CaptureFixture[str]) -> None:
        #: Given
        model = WorkspaceModel(corpora=(), skills_dirs=(), skill_locations=(), outside_symlinks=(), load_failures=())

        #: When
        returned = exit_on_unlistable_directory(model)

        #: Then
        assert returned is None, 'a model that recorded nothing is no reason to stop'
        assert capsys.readouterr().err == '', 'and nothing is written'

    def test_exit_on_unlistable_directory_with_a_failure_of_another_unit_returns(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, EmptyStructureSpec())
        model = WorkspaceModel(
            corpora=(), skills_dirs=(), skill_locations=(), outside_symlinks=(), load_failures=(failure,)
        )

        #: When
        returned = exit_on_unlistable_directory(model)

        #: Then
        assert returned is None, 'such a failure is a diagnostic of the run, not a reason to stop it'
        assert capsys.readouterr().err == '', 'and the command writes nothing for it'

    def test_exit_on_unlistable_directory_with_one_among_other_failures_reports_it_and_exits_two(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        other = LoadFailure(_PATH, EmptyStructureSpec())
        unlistable = LoadFailure(RootRelativePath.parse('docs/__meta__'), UnlistableDirectory(_REFUSAL))
        model = WorkspaceModel(
            corpora=(), skills_dirs=(), skill_locations=(), outside_symlinks=(), load_failures=(other, unlistable)
        )

        #: When
        with pytest.raises(typer.Exit) as exc_info:
            exit_on_unlistable_directory(model)

        #: Then
        assert exc_info.value.exit_code == ExitStatus.FAILURE, 'nothing can be checked, so the run is an error'
        assert capsys.readouterr().err == 'error: cannot list directory docs/__meta__: permission denied\n', (
            'the directory is printed as a failure, as it is when the root cannot be found'
        )
