"""Reporting a failure a command cannot recover from: the error, then the errors beneath it."""

from typing import Final

import pytest

from lorecraft.core.error import Error
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import CorpusName
from lorecraft.project.schemas import (
    CorpusSpecName,
    SectionName,
    StructureSpecProblem,
)
from lorecraft.project.workspace import (
    AdjacentAnyRuns,
    CyclicFrontmatterSchemaRef,
    EmptyStructureSpec,
    ForbiddenOutlineSections,
    ForeignFrontmatterDialect,
    IdentifiedFrontmatterSchema,
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
    UnresolvableFrontmatterSchemaRef,
    UnresolvableSkillEntry,
    UnresolvableSkillFile,
    UnresolvableSkillsDirectory,
    UntypedFrontmatterSchema,
    WorkspaceModel,
)
from lorecraft.vfs import (
    OsRefusal,
    Utf8Failure,
)

from ..failure import report_failure, report_first_load_failure, report_load_failure
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
            '  caused by: [Errno 13] Permission denied\n'
        ), 'each link is a line, the foreign exception at the bottom included'

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


_PATH: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.spec.json')
_DOCS: Final[RootRelativePath] = RootRelativePath.parse('docs')
_CORPUS: Final[CorpusName] = CorpusName.parse('code')
_CORPUS_DIR: Final[RootRelativePath] = RootRelativePath.parse('docs/code')
_SPEC_NAME: Final[CorpusSpecName] = CorpusSpecName(_CORPUS)
_SKILLS_DIR: Final[RootRelativePath] = RootRelativePath.parse('.claude/skills')
# The directory, entry and file a link in the skills layout leads to, as the repository's errors name them.
_TARGET_DIR: Final[RootRelativePath] = RootRelativePath.parse('shared/skills')
_ENTRY: Final[RootRelativePath] = RootRelativePath.parse('.claude/skills/review')
_ENTRY_FILE: Final[RootRelativePath] = RootRelativePath.parse('.claude/skills/review/SKILL.md')
_TARGET_FILE: Final[RootRelativePath] = RootRelativePath.parse('shared/review/SKILL.md')
_INNER: Final[RootRelativePath] = RootRelativePath.parse('shared/review/inner')
_PROBLEMS: Final[tuple[StructureSpecProblem, StructureSpecProblem]] = (
    StructureSpecProblem(('outline',), 'Field required'),
    StructureSpecProblem(('tokens',), 'not a number'),
)
_REFUSAL: Final[OsRefusal] = OsRefusal.PERMISSION_DENIED


@pytest.mark.unit
class TestReportLoadFailure:
    def test_report_load_failure_with_unreadable_structure_file_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, UnreadableStructureFile(_SPEC_NAME, _REFUSAL))
        expected = (
            'error: cannot read the structure schema code\n'
            '  caused by: cannot read file docs/__meta__/code.spec.json: permission denied\n'
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_unrecorded_structure_file_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, UnrecordedStructureFile(_SPEC_NAME))
        expected = (
            'error: cannot read the structure schema code\n'
            '  caused by: cannot read file docs/__meta__/code.spec.json: not in the snapshot\n'
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_non_utf8_structure_file_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        decode_error = UnicodeDecodeError('utf-8', b'\xe9', 0, 1, 'invalid continuation byte')
        failure = LoadFailure(_PATH, NonUtf8StructureFile(Utf8Failure.from_error(decode_error)))
        expected = 'error: file docs/__meta__/code.spec.json is not UTF-8\n'

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_undecodable_structure_spec_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, UndecodableStructureSpec(_PROBLEMS))
        expected = (
            'error: invalid structure schema docs/__meta__/code.spec.json: '
            'outline: Field required; tokens: not a number\n'
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_empty_structure_spec_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, EmptyStructureSpec())
        expected = (
            'error: invalid structure schema docs/__meta__/code.spec.json: states no rule, so it would check nothing\n'
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_repeated_outline_sections_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, RepeatedOutlineSections((SectionName('Usage'),)))
        expected = (
            'error: invalid structure schema docs/__meta__/code.spec.json: '
            "names sections more than once in the outline: ['Usage']\n"
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_repeated_forbidden_sections_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, RepeatedForbiddenSections((SectionName('Changelog'),)))
        expected = (
            'error: invalid structure schema docs/__meta__/code.spec.json: '
            "forbids sections more than once: ['Changelog']\n"
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_forbidden_outline_sections_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, ForbiddenOutlineSections((SectionName('Usage'),)))
        expected = (
            'error: invalid structure schema docs/__meta__/code.spec.json: '
            "forbids sections its own outline names: ['Usage']\n"
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_adjacent_any_runs_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, AdjacentAnyRuns())
        expected = 'error: invalid structure schema docs/__meta__/code.spec.json: places two `any` runs side by side\n'

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_invalid_title_pattern_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, InvalidTitlePattern('(', 'missing )'))
        expected = (
            'error: invalid structure schema docs/__meta__/code.spec.json: '
            "title pattern '(' is not a valid regular expression\n"
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_invalid_frontmatter_schema_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, InvalidFrontmatterSchema('5 is not valid'))
        expected = (
            'error: invalid structure schema docs/__meta__/code.spec.json: '
            'frontmatter is not a valid JSON Schema: 5 is not valid\n'
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_frontmatter_schema_id_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, IdentifiedFrontmatterSchema())
        expected = (
            'error: invalid structure schema docs/__meta__/code.spec.json: frontmatter schema may not carry $id\n'
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_foreign_frontmatter_dialect_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, ForeignFrontmatterDialect('draft-07'))
        expected = (
            'error: invalid structure schema docs/__meta__/code.spec.json: '
            "frontmatter schema names 'draft-07' in $schema; "
            'only https://json-schema.org/draft/2020-12/schema is allowed\n'
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_unresolvable_frontmatter_schema_ref_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, UnresolvableFrontmatterSchemaRef('#/$defs/missing'))
        expected = (
            'error: invalid structure schema docs/__meta__/code.spec.json: '
            "frontmatter schema holds a $ref '#/$defs/missing' that does not resolve inside it\n"
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report names the reference'

    def test_report_load_failure_with_cyclic_frontmatter_schema_ref_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, CyclicFrontmatterSchemaRef('#'))
        expected = (
            'error: invalid structure schema docs/__meta__/code.spec.json: '
            "frontmatter schema holds a $ref '#' that leads back to itself with no keyword in between\n"
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report names the reference'

    def test_report_load_failure_with_untyped_frontmatter_schema_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_PATH, UntypedFrontmatterSchema())
        expected = (
            'error: invalid structure schema docs/__meta__/code.spec.json: '
            'frontmatter schema root must state "type": "object"\n'
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_unlistable_directory_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_DOCS, UnlistableDirectory(_REFUSAL))
        expected = 'error: cannot list directory docs: permission denied\n'

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_unlistable_corpus_directory_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_CORPUS_DIR, UnlistableCorpusDirectory(_CORPUS, _REFUSAL))
        expected = (
            'error: cannot list the documents of corpus code\n'
            '  caused by: cannot list directory docs/code: permission denied\n'
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_unresolvable_skills_directory_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_SKILLS_DIR, UnresolvableSkillsDirectory(_REFUSAL))
        expected = 'error: cannot resolve directory .claude/skills: permission denied\n'

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_uninspectable_skills_directory_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_SKILLS_DIR, UninspectableSkillsDirectory(_INNER, _REFUSAL))
        expected = 'error: cannot inspect entry shared/review/inner: permission denied\n'

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_unlistable_skills_directory_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_SKILLS_DIR, UnlistableSkillsDirectory(_TARGET_DIR, _REFUSAL))
        expected = (
            'error: cannot list the skills in shared/skills\n'
            '  caused by: cannot list directory shared/skills: permission denied\n'
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_unresolvable_skill_entry_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_ENTRY, UnresolvableSkillEntry(_REFUSAL))
        expected = (
            'error: cannot resolve skill entry .claude/skills/review\n'
            '  caused by: cannot resolve directory .claude/skills/review: permission denied\n'
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_uninspectable_skill_entry_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_ENTRY, UninspectableSkillEntry(_INNER, _REFUSAL))
        expected = (
            'error: cannot resolve skill entry .claude/skills/review\n'
            '  caused by: cannot inspect entry shared/review/inner: permission denied\n'
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_unlistable_skill_directory_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_ENTRY, UnlistableSkillDirectory(_TARGET_DIR, _REFUSAL))
        expected = (
            'error: cannot look for SKILL.md in shared/skills\n'
            '  caused by: cannot list directory shared/skills: permission denied\n'
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_unresolvable_skill_file_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_ENTRY_FILE, UnresolvableSkillFile(_TARGET_FILE, _REFUSAL))
        expected = (
            'error: cannot resolve shared/review/SKILL.md\n'
            '  caused by: cannot resolve file shared/review/SKILL.md: permission denied\n'
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'

    def test_report_load_failure_with_uninspectable_skill_file_writes_what_the_replaced_error_wrote(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        failure = LoadFailure(_ENTRY_FILE, UninspectableSkillFile(_TARGET_FILE, _INNER, _REFUSAL))
        expected = (
            'error: cannot resolve shared/review/SKILL.md\n'
            '  caused by: cannot inspect entry shared/review/inner: permission denied\n'
        )

        #: When
        report_load_failure(failure)

        #: Then
        assert capsys.readouterr().err == expected, 'the interim report is what the raised error wrote'


@pytest.mark.unit
class TestExitOnLoadFailure:
    def test_report_first_load_failure_with_no_failure_returns_none(self) -> None:
        #: Given
        model = WorkspaceModel(
            corpora=FrozenMapping({}),
            skills_dirs=frozenset(),
            skill_locations=FrozenMapping({}),
            outside_symlinks=FrozenMapping({}),
            load_failures=(),
        )

        #: When
        result = report_first_load_failure(model)

        #: Then
        assert result is None, 'a model that recorded nothing is no reason to stop'

    def test_report_first_load_failure_with_failures_reports_the_first_and_returns_failure(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        first = LoadFailure(RootRelativePath.parse('docs/__meta__'), UnlistableDirectory(_REFUSAL))
        second = LoadFailure(RootRelativePath.parse('docs'), UnlistableDirectory(_REFUSAL))
        model = WorkspaceModel(
            corpora=FrozenMapping({}),
            skills_dirs=frozenset(),
            skill_locations=FrozenMapping({}),
            outside_symlinks=FrozenMapping({}),
            load_failures=(first, second),
        )

        #: When
        status = report_first_load_failure(model)

        #: Then
        assert status is ExitStatus.FAILURE, 'the run exits as an error did'
        assert capsys.readouterr().err == 'error: cannot list directory docs/__meta__: permission denied\n', (
            'only the first failure is reported, as only the first error was raised'
        )
