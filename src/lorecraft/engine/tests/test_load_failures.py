"""The run's report of each load failure the model lists: one engine condition, at the failure's own path."""

from typing import Final

import pytest

from lorecraft.core.lines import ByteOffset, Line
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.corpus import CorpusName
from lorecraft.project.schemas import CorpusSpecName, SectionName, StructureSpecProblem
from lorecraft.project.workspace import (
    AdjacentAnyRuns,
    CyclicFrontmatterSchemaRefKeyword,
    EmptyStructureSpec,
    ForbiddenOutlineSections,
    ForeignFrontmatterDialect,
    IdentifiedFrontmatterSchema,
    InvalidFrontmatterSchema,
    InvalidTitlePattern,
    LoadFailure,
    LoadFailureCondition,
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
    UnresolvableFrontmatterSchemaRefKeyword,
    UnresolvableSkillEntry,
    UnresolvableSkillFile,
    UnresolvableSkillsDirectory,
    UntypedFrontmatterSchema,
    WorkspaceModel,
)
from lorecraft.rules.declaration import EngineCondition
from lorecraft.rules.engine import (
    RefusedOperation,
    invalid_utf8,
    malformed_structure_file,
    unreadable_path,
    unusable_structure_file,
)
from lorecraft.rules.engine.unreadable_path import NotARegularFile, Refused
from lorecraft.rules.report import LoadFailureReport
from lorecraft.vfs import OsRefusal, Utf8Failure, Utf8Reason

from ..load_failures import UnlistableRoot, report_load_failures

_PATH: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.spec.json')
_ENTRY: Final[RootRelativePath] = RootRelativePath.parse('.claude/skills/review')
_ON_THE_WAY: Final[RootRelativePath] = RootRelativePath.parse('shared/skills')
_REFUSAL: Final[OsRefusal] = OsRefusal.PERMISSION_DENIED
_UTF8: Final[Utf8Failure] = Utf8Failure(
    line=Line(NonZeroUnsignedInt(3)),
    offset=ByteOffset(UnsignedInt(47)),
    invalid=b'\xe9',
    reason=Utf8Reason.INVALID_CONTINUATION_BYTE,
)


def _model(*failures: LoadFailure) -> WorkspaceModel:
    """A model that holds nothing but the failures it listed.

    Args:
        failures: The load failures the model lists, in order.
    """
    return WorkspaceModel(
        corpus_values=frozenset(),
        skills_dirs=frozenset(),
        skill_locations=FrozenMapping({}),
        outside_symlinks=FrozenMapping({}),
        load_failures=tuple(failures),
    )


def _condition_of(condition: LoadFailureCondition, path: RootRelativePath = _PATH) -> EngineCondition:
    """The one engine condition a model that listed one failure is reported as.

    Args:
        condition: What failed.
        path: Where it failed.
    """
    result = report_load_failures(_model(LoadFailure(path, condition)))
    assert not isinstance(result, UnlistableRoot), 'the failure is one the run reports'
    (report,) = result
    return report.occurrence


@pytest.mark.unit
class TestReportLoadFailures:
    def test_report_load_failures_with_no_failure_reports_none(self) -> None:
        #: Given
        model = _model()

        #: When
        reports = report_load_failures(model)

        #: Then
        assert reports == (), 'a model that listed nothing has nothing to report'

    def test_report_load_failures_with_two_failures_files_each_at_its_own_path(self) -> None:
        #: Given
        first = LoadFailure(_PATH, EmptyStructureSpec())
        second = LoadFailure(_ENTRY, UnresolvableSkillEntry(_REFUSAL))
        model = _model(first, second)

        #: When
        reports = report_load_failures(model)

        #: Then
        assert reports == (
            LoadFailureReport(
                _PATH, malformed_structure_file.MalformedStructureFile(cause=malformed_structure_file.NoRuleStated())
            ),
            LoadFailureReport(
                _ENTRY,
                unreadable_path.UnreadablePath(
                    failed_at=_ENTRY, cause=Refused(operation=RefusedOperation.RESOLVE, refusal=_REFUSAL)
                ),
            ),
        ), 'one report per failure, in the order the model lists them, each at its own path'

    def test_report_load_failures_with_an_unlistable_docs_directory_returns_it_as_the_unlistable_root(self) -> None:
        #: Given
        failure = LoadFailure(RootRelativePath.parse('docs'), UnlistableDirectory(_REFUSAL))
        model = _model(failure)

        #: When
        result = report_load_failures(model)

        #: Then
        assert result == UnlistableRoot(failure), 'no diagnostic stands for it: the command stops the run on it'

    def test_report_load_failures_with_an_unlistable_directory_among_others_returns_the_first_one(self) -> None:
        #: Given
        other = LoadFailure(_PATH, EmptyStructureSpec())
        first = LoadFailure(RootRelativePath.parse('docs/__meta__'), UnlistableDirectory(_REFUSAL))
        second = LoadFailure(RootRelativePath.parse('docs'), UnlistableDirectory(_REFUSAL))
        model = _model(other, first, second)

        #: When
        result = report_load_failures(model)

        #: Then
        assert result == UnlistableRoot(first), 'the failure is the first the model listed, and no report is returned'

    def test_report_load_failures_with_an_unreadable_structure_file_reports_the_refusal(self) -> None:
        #: Given
        condition = UnreadableStructureFile(CorpusSpecName(CorpusName.parse('code')), _REFUSAL)

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == unreadable_path.UnreadablePath(
            failed_at=_PATH, cause=Refused(operation=RefusedOperation.READ, refusal=_REFUSAL)
        ), 'the condition holds the read that was refused and why'

    def test_report_load_failures_with_an_unrecorded_structure_file_reports_it_unreadable_without_a_refusal(
        self,
    ) -> None:
        #: Given
        condition = UnrecordedStructureFile(CorpusSpecName(CorpusName.parse('code')))

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == unreadable_path.UnreadablePath(failed_at=_PATH, cause=NotARegularFile()), (
            'no regular file is there to read, so there is no refusal to name'
        )

    def test_report_load_failures_with_a_structure_file_that_is_not_utf8_reports_invalid_utf8(self) -> None:
        #: Given
        condition = NonUtf8StructureFile(_UTF8)

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == invalid_utf8.InvalidUtf8(failure=_UTF8), (
            'a structure file that does not decode is a file that does not decode, reported as any other is'
        )

    def test_report_load_failures_with_an_undecodable_structure_spec_reports_every_problem(self) -> None:
        #: Given
        condition = UndecodableStructureSpec(
            (
                StructureSpecProblem(('max_tokens',), 'Extra inputs are not permitted'),
                StructureSpecProblem(('tokens',), 'Field required'),
            )
        )

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == malformed_structure_file.MalformedStructureFile(
            cause=malformed_structure_file.FormatViolated(
                problems=('max_tokens: Extra inputs are not permitted', 'tokens: Field required')
            )
        ), 'the condition holds each problem the decoder found'

    def test_report_load_failures_with_an_empty_structure_spec_reports_a_file_stating_no_rule(self) -> None:
        #: Given
        condition = EmptyStructureSpec()

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == malformed_structure_file.MalformedStructureFile(
            cause=malformed_structure_file.NoRuleStated()
        ), 'the file would check nothing'

    def test_report_load_failures_with_a_repeated_outline_section_reports_the_sections(self) -> None:
        #: Given
        condition = RepeatedOutlineSections((SectionName('Overview'),))

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == unusable_structure_file.UnusableStructureFile(
            cause=unusable_structure_file.RepeatedOutlineSection(sections=(SectionName('Overview'),))
        ), 'the condition names the repeated sections'

    def test_report_load_failures_with_a_repeated_forbidden_section_reports_the_sections(self) -> None:
        #: Given
        condition = RepeatedForbiddenSections((SectionName('Draft'),))

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == unusable_structure_file.UnusableStructureFile(
            cause=unusable_structure_file.RepeatedForbiddenSection(sections=(SectionName('Draft'),))
        ), 'the condition names the sections forbidden twice'

    def test_report_load_failures_with_a_forbidden_outline_section_reports_the_sections(self) -> None:
        #: Given
        condition = ForbiddenOutlineSections((SectionName('Overview'),))

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == unusable_structure_file.UnusableStructureFile(
            cause=unusable_structure_file.ForbiddenOutlineSection(sections=(SectionName('Overview'),))
        ), 'the condition names the sections the outline and the forbidden list both hold'

    def test_report_load_failures_with_adjacent_any_runs_reports_them(self) -> None:
        #: Given
        condition = AdjacentAnyRuns()

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == unusable_structure_file.UnusableStructureFile(
            cause=unusable_structure_file.AdjacentAnyRuns()
        ), 'the outline places two runs side by side'

    def test_report_load_failures_with_an_invalid_title_pattern_reports_the_pattern_and_the_problem(self) -> None:
        #: Given
        condition = InvalidTitlePattern('[A-Z', 'unterminated character set at position 0')

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == unusable_structure_file.UnusableStructureFile(
            cause=unusable_structure_file.InvalidTitlePattern(
                pattern='[A-Z', problem='unterminated character set at position 0'
            )
        ), 'the condition holds the pattern as written and what the compiler rejected'

    def test_report_load_failures_with_an_invalid_frontmatter_schema_reports_the_problem(self) -> None:
        #: Given
        condition = InvalidFrontmatterSchema("'name' is not of type 'array'")

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == unusable_structure_file.UnusableStructureFile(
            cause=unusable_structure_file.InvalidFrontmatterSchema(problem="'name' is not of type 'array'")
        ), 'the condition holds what the meta-schema rejected'

    def test_report_load_failures_with_a_frontmatter_schema_id_reports_it(self) -> None:
        #: Given
        condition = IdentifiedFrontmatterSchema()

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == unusable_structure_file.UnusableStructureFile(
            cause=unusable_structure_file.IdentifiedFrontmatterSchema()
        ), 'a schema carries `$id`'

    def test_report_load_failures_with_a_foreign_frontmatter_dialect_reports_the_dialect(self) -> None:
        #: Given
        condition = ForeignFrontmatterDialect('http://json-schema.org/draft-07/schema#')

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == unusable_structure_file.UnusableStructureFile(
            cause=unusable_structure_file.ForeignFrontmatterDialect(dialect="'http://json-schema.org/draft-07/schema#'")
        ), 'the condition holds what `$schema` named'

    def test_report_load_failures_with_an_unresolvable_frontmatter_schema_ref_reports_the_reference(self) -> None:
        #: Given
        condition = UnresolvableFrontmatterSchemaRefKeyword('#/$defs/missing')

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == unusable_structure_file.UnusableStructureFile(
            cause=unusable_structure_file.UnresolvableFrontmatterSchemaRefKeyword(ref="'#/$defs/missing'")
        ), 'the condition holds what `$ref` named'

    def test_report_load_failures_with_a_cyclic_frontmatter_schema_ref_reports_the_reference(self) -> None:
        #: Given
        condition = CyclicFrontmatterSchemaRefKeyword('#')

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == unusable_structure_file.UnusableStructureFile(
            cause=unusable_structure_file.CyclicFrontmatterSchemaRefKeyword(ref="'#'")
        ), 'the condition holds what `$ref` named'

    def test_report_load_failures_with_an_untyped_frontmatter_schema_reports_it(self) -> None:
        #: Given
        condition = UntypedFrontmatterSchema()

        #: When
        occurrence = _condition_of(condition)

        #: Then
        assert occurrence == unusable_structure_file.UnusableStructureFile(
            cause=unusable_structure_file.UntypedFrontmatterSchema()
        ), 'the root states no type'

    def test_report_load_failures_with_an_unlistable_corpus_directory_reports_the_corpus_and_the_refusal(self) -> None:
        #: Given
        condition = UnlistableCorpusDirectory(CorpusName.parse('code'), _REFUSAL)
        path = RootRelativePath.parse('docs/code')

        #: When
        occurrence = _condition_of(condition, path)

        #: Then
        assert occurrence == unreadable_path.UnreadablePath(
            failed_at=RootRelativePath.parse('docs/code'),
            cause=Refused(operation=RefusedOperation.LIST, refusal=_REFUSAL),
        ), 'the condition holds the corpus directory whose listing was refused and why'

    def test_report_load_failures_with_a_skills_directory_that_cannot_be_resolved_reports_what_was_refused_where(
        self,
    ) -> None:
        #: Given
        condition = UnresolvableSkillsDirectory(_REFUSAL)
        path = _ENTRY

        #: When
        occurrence = _condition_of(condition, path)

        #: Then
        assert occurrence == unreadable_path.UnreadablePath(
            failed_at=_ENTRY, cause=Refused(operation=RefusedOperation.RESOLVE, refusal=_REFUSAL)
        ), 'the condition holds the operation, the path it was refused at and why'

    def test_report_load_failures_with_a_skills_directory_that_cannot_be_inspected_reports_what_was_refused_where(
        self,
    ) -> None:
        #: Given
        condition = UninspectableSkillsDirectory(_ON_THE_WAY, _REFUSAL)
        path = _ENTRY

        #: When
        occurrence = _condition_of(condition, path)

        #: Then
        assert occurrence == unreadable_path.UnreadablePath(
            failed_at=_ON_THE_WAY, cause=Refused(operation=RefusedOperation.INSPECT, refusal=_REFUSAL)
        ), 'the condition holds the operation, the path it was refused at and why'

    def test_report_load_failures_with_a_skills_directory_that_cannot_be_listed_reports_what_was_refused_where(
        self,
    ) -> None:
        #: Given
        condition = UnlistableSkillsDirectory(_ON_THE_WAY, _REFUSAL)
        path = _ENTRY

        #: When
        occurrence = _condition_of(condition, path)

        #: Then
        assert occurrence == unreadable_path.UnreadablePath(
            failed_at=_ON_THE_WAY, cause=Refused(operation=RefusedOperation.LIST, refusal=_REFUSAL)
        ), 'the condition holds the operation, the path it was refused at and why'

    def test_report_load_failures_with_a_skill_entry_that_cannot_be_resolved_reports_what_was_refused_where(
        self,
    ) -> None:
        #: Given
        condition = UnresolvableSkillEntry(_REFUSAL)
        path = _ENTRY

        #: When
        occurrence = _condition_of(condition, path)

        #: Then
        assert occurrence == unreadable_path.UnreadablePath(
            failed_at=_ENTRY, cause=Refused(operation=RefusedOperation.RESOLVE, refusal=_REFUSAL)
        ), 'the condition holds the operation, the path it was refused at and why'

    def test_report_load_failures_with_a_skill_entry_that_cannot_be_inspected_reports_what_was_refused_where(
        self,
    ) -> None:
        #: Given
        condition = UninspectableSkillEntry(_ON_THE_WAY, _REFUSAL)
        path = _ENTRY

        #: When
        occurrence = _condition_of(condition, path)

        #: Then
        assert occurrence == unreadable_path.UnreadablePath(
            failed_at=_ON_THE_WAY, cause=Refused(operation=RefusedOperation.INSPECT, refusal=_REFUSAL)
        ), 'the condition holds the operation, the path it was refused at and why'

    def test_report_load_failures_with_a_skill_entry_that_cannot_be_listed_reports_what_was_refused_where(self) -> None:
        #: Given
        condition = UnlistableSkillDirectory(_ON_THE_WAY, _REFUSAL)
        path = _ENTRY

        #: When
        occurrence = _condition_of(condition, path)

        #: Then
        assert occurrence == unreadable_path.UnreadablePath(
            failed_at=_ON_THE_WAY, cause=Refused(operation=RefusedOperation.LIST, refusal=_REFUSAL)
        ), 'the condition holds the operation, the path it was refused at and why'

    def test_report_load_failures_with_a_skill_file_that_cannot_be_resolved_reports_what_was_refused_where(
        self,
    ) -> None:
        #: Given
        condition = UnresolvableSkillFile(_ON_THE_WAY, _REFUSAL)
        path = _ENTRY / PathComponent.parse('SKILL.md')

        #: When
        occurrence = _condition_of(condition, path)

        #: Then
        assert occurrence == unreadable_path.UnreadablePath(
            failed_at=_ON_THE_WAY, cause=Refused(operation=RefusedOperation.RESOLVE, refusal=_REFUSAL)
        ), 'the condition holds the operation, the path it was refused at and why'

    def test_report_load_failures_with_a_skill_file_that_cannot_be_inspected_reports_what_was_refused_where(
        self,
    ) -> None:
        #: Given
        condition = UninspectableSkillFile(_ENTRY / PathComponent.parse('SKILL.md'), _ON_THE_WAY, _REFUSAL)
        path = _ENTRY / PathComponent.parse('SKILL.md')

        #: When
        occurrence = _condition_of(condition, path)

        #: Then
        assert occurrence == unreadable_path.UnreadablePath(
            failed_at=_ON_THE_WAY, cause=Refused(operation=RefusedOperation.INSPECT, refusal=_REFUSAL)
        ), 'the condition holds the operation, the path it was refused at and why'
