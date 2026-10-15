"""The order diagnostics print in, an engine diagnostic's severity, and the diagnostics each subject report holds."""

import pytest

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.skill import SkillRef
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.engine.invalid_utf8 import InvalidUtf8
from lorecraft.rules.engine.malformed_structure_file import MalformedStructureFile, NoRuleStated
from lorecraft.vfs import ByteOffset, ResolvedPath, Utf8Failure, Utf8Line, Utf8Reason

from ..identity import Severity
from ..report import (
    CheckedDocument,
    CheckedLayoutEntry,
    CheckedSkillFile,
    EngineDiagnostic,
    LoadFailureReport,
    RuleDiagnostic,
    SkippedSubject,
    UndecodableSubject,
    diagnostic_order,
)
from .sample_rules.rendered_message.long_line import LongLine
from .sample_rules.token_count.sample_condition import SampleCondition
from .sample_rules.valid.outline.empty_line import EmptyLine
from .sample_rules.valid.trailing_space import TrailingSpace
from .sample_rules.valid.uppercase_entry import UppercaseEntry


def _failure(line: int) -> Utf8Failure:
    return Utf8Failure(
        line=Utf8Line(line),
        offset=ByteOffset(31),
        invalid=b'\xe9',
        reason=Utf8Reason.INVALID_CONTINUATION_BYTE,
    )


@pytest.mark.unit
class TestDiagnosticOrder:
    def test_diagnostic_order_with_paths_differing_compares_them_as_posix_strings(self) -> None:
        #: Given
        occurrence = TrailingSpace(spec=None, line=LineNumber(NonZeroUnsignedInt(1)))
        nested = RuleDiagnostic(RootRelativePath.parse('a/b.md'), occurrence, Severity.ERROR)
        hyphenated = RuleDiagnostic(RootRelativePath.parse('a-b/c.md'), occurrence, Severity.ERROR)

        #: When
        ordered = sorted([nested, hyphenated], key=diagnostic_order)

        #: Then
        assert ordered == [hyphenated, nested], (
            'a path compares as its string, where `-` is below `/`, not component by component'
        )

    def test_diagnostic_order_with_paths_differing_in_case_puts_uppercase_first(self) -> None:
        #: Given
        occurrence = TrailingSpace(spec=None, line=LineNumber(NonZeroUnsignedInt(1)))
        lowercase = RuleDiagnostic(RootRelativePath.parse('docs/a.md'), occurrence, Severity.ERROR)
        uppercase = RuleDiagnostic(RootRelativePath.parse('docs/B.md'), occurrence, Severity.ERROR)

        #: When
        ordered = sorted([lowercase, uppercase], key=diagnostic_order)

        #: Then
        assert ordered == [uppercase, lowercase], 'a path compares by code point, never by locale'

    def test_diagnostic_order_with_lines_differing_puts_the_earlier_line_first(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/a.md')
        later = RuleDiagnostic(path, TrailingSpace(spec=None, line=LineNumber(NonZeroUnsignedInt(10))), Severity.ERROR)
        earlier = RuleDiagnostic(path, TrailingSpace(spec=None, line=LineNumber(NonZeroUnsignedInt(2))), Severity.ERROR)

        #: When
        ordered = sorted([later, earlier], key=diagnostic_order)

        #: Then
        assert ordered == [earlier, later], 'lines compare as numbers, so line 2 is before line 10'

    def test_diagnostic_order_with_the_whole_subject_and_a_line_puts_the_whole_subject_first(self) -> None:
        #: Given
        path = RootRelativePath.parse('skills/a')
        at_line = RuleDiagnostic(path, TrailingSpace(spec=None, line=LineNumber(NonZeroUnsignedInt(1))), Severity.ERROR)
        whole_subject = RuleDiagnostic(path, UppercaseEntry(spec=None), Severity.WARNING)

        #: When
        ordered = sorted([at_line, whole_subject], key=diagnostic_order)

        #: Then
        assert ordered == [whole_subject, at_line], (
            'the whole subject is before every line, whatever the severity after it'
        )

    def test_diagnostic_order_with_severities_differing_puts_the_error_first(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/a.md')
        occurrence = TrailingSpace(spec=None, line=LineNumber(NonZeroUnsignedInt(1)))
        warning = RuleDiagnostic(path, occurrence, Severity.WARNING)
        error = RuleDiagnostic(path, occurrence, Severity.ERROR)

        #: When
        ordered = sorted([warning, error], key=diagnostic_order)

        #: Then
        assert ordered == [error, warning], 'an error is before a warning'

    def test_diagnostic_order_with_codes_differing_compares_them_as_printed(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/a.md')
        second = RuleDiagnostic(path, TrailingSpace(spec=None, line=LineNumber(NonZeroUnsignedInt(1))), Severity.ERROR)
        first = RuleDiagnostic(path, EmptyLine(spec=None, line=LineNumber(NonZeroUnsignedInt(1))), Severity.ERROR)

        #: When
        ordered = sorted([second, first], key=diagnostic_order)

        #: Then
        assert ordered == [first, second], 'SMP001 is before SMP002'

    def test_diagnostic_order_with_messages_differing_compares_the_message_text(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/a.md')
        ninety = RuleDiagnostic(
            path, LongLine(spec=None, line=LineNumber(NonZeroUnsignedInt(1)), length=90), Severity.WARNING
        )
        eighty_one = RuleDiagnostic(
            path, LongLine(spec=None, line=LineNumber(NonZeroUnsignedInt(1)), length=81), Severity.WARNING
        )

        #: When
        ordered = sorted([ninety, eighty_one], key=diagnostic_order)

        #: Then
        assert ordered == [eighty_one, ninety], 'the message text breaks a tie on every other step'

    def test_diagnostic_order_with_any_input_order_sorts_by_path_location_severity_and_code(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/a.md')
        long_line = RuleDiagnostic(
            path, LongLine(spec=None, line=LineNumber(NonZeroUnsignedInt(3)), length=81), Severity.WARNING
        )
        trailing_space = RuleDiagnostic(
            path, TrailingSpace(spec=None, line=LineNumber(NonZeroUnsignedInt(3))), Severity.ERROR
        )
        empty_line = RuleDiagnostic(path, EmptyLine(spec=None, line=LineNumber(NonZeroUnsignedInt(3))), Severity.ERROR)
        whole_subject = RuleDiagnostic(path, UppercaseEntry(spec=None), Severity.ERROR)
        next_path = RuleDiagnostic(
            RootRelativePath.parse('docs/b.md'),
            EmptyLine(spec=None, line=LineNumber(NonZeroUnsignedInt(1))),
            Severity.ERROR,
        )
        diagnostics = [long_line, trailing_space, empty_line, whole_subject, next_path]

        #: When
        ordered = sorted(diagnostics, key=diagnostic_order)

        #: Then
        assert ordered == [whole_subject, empty_line, trailing_space, long_line, next_path], (
            'the diagnostics sort by path, location, severity and code'
        )

    def test_diagnostic_order_with_any_input_order_in_reverse_input_order_sorts_to_the_same_output(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/a.md')
        long_line = RuleDiagnostic(
            path, LongLine(spec=None, line=LineNumber(NonZeroUnsignedInt(3)), length=81), Severity.WARNING
        )
        trailing_space = RuleDiagnostic(
            path, TrailingSpace(spec=None, line=LineNumber(NonZeroUnsignedInt(3))), Severity.ERROR
        )
        empty_line = RuleDiagnostic(path, EmptyLine(spec=None, line=LineNumber(NonZeroUnsignedInt(3))), Severity.ERROR)
        whole_subject = RuleDiagnostic(path, UppercaseEntry(spec=None), Severity.ERROR)
        next_path = RuleDiagnostic(
            RootRelativePath.parse('docs/b.md'),
            EmptyLine(spec=None, line=LineNumber(NonZeroUnsignedInt(1))),
            Severity.ERROR,
        )
        diagnostics = [long_line, trailing_space, empty_line, whole_subject, next_path]
        expected = sorted(diagnostics, key=diagnostic_order)
        reversed_diagnostics = list(reversed(diagnostics))

        #: When
        ordered = sorted(reversed_diagnostics, key=diagnostic_order)

        #: Then
        assert ordered == expected, 'the order is total, so the input order never shows in the output'

    def test_diagnostic_order_with_an_engine_condition_and_a_rule_sorts_them_by_line(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/code/a.md')
        at_line = RuleDiagnostic(path, TrailingSpace(spec=None, line=LineNumber(NonZeroUnsignedInt(2))), Severity.ERROR)
        condition = EngineDiagnostic(path, InvalidUtf8(failure=_failure(1)))

        #: When
        ordered = sorted([at_line, condition], key=diagnostic_order)

        #: Then
        assert ordered == [condition, at_line], 'an engine condition sorts by the same key a rule does'


@pytest.mark.unit
class TestEngineDiagnostic:
    def test_severity_of_an_engine_diagnostic_is_its_condition_class_severity(self) -> None:
        #: Given
        # the sample condition fixes `warning`, so the severity cannot be one every engine diagnostic shares
        diagnostic = EngineDiagnostic(RootRelativePath.parse('docs/code/a.md'), SampleCondition())

        #: When
        severity = diagnostic.severity

        #: Then
        assert severity is Severity.WARNING, "an engine diagnostic reports at its condition class's `SEVERITY`"


@pytest.mark.unit
class TestCheckedSkillFile:
    def test_checked_skill_file_with_diagnostics_out_of_order_holds_them_in_diagnostic_order(self) -> None:
        #: Given
        ref = SkillRef(ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review'))
        later = RuleDiagnostic(
            ref.path, TrailingSpace(spec=None, line=LineNumber(NonZeroUnsignedInt(10))), Severity.ERROR
        )
        earlier = RuleDiagnostic(
            ref.path, TrailingSpace(spec=None, line=LineNumber(NonZeroUnsignedInt(2))), Severity.ERROR
        )

        #: When
        subject = CheckedSkillFile(ref, diagnostics=(later, earlier))

        #: Then
        assert subject.diagnostics == (earlier, later), 'a report holds its diagnostics in output order, however built'


@pytest.mark.unit
class TestCheckedDocument:
    def test_checked_document_with_diagnostics_out_of_order_holds_them_in_diagnostic_order(self) -> None:
        #: Given
        ref = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('a'))
        later = RuleDiagnostic(
            ref.path, TrailingSpace(spec=None, line=LineNumber(NonZeroUnsignedInt(10))), Severity.ERROR
        )
        earlier = RuleDiagnostic(
            ref.path, TrailingSpace(spec=None, line=LineNumber(NonZeroUnsignedInt(2))), Severity.ERROR
        )

        #: When
        subject = CheckedDocument(ref, diagnostics=(later, earlier), ungoverned=())

        #: Then
        assert subject.diagnostics == (earlier, later), 'a report holds its diagnostics in output order, however built'


@pytest.mark.unit
class TestCheckedLayoutEntry:
    def test_checked_layout_entry_with_diagnostics_out_of_order_holds_them_in_diagnostic_order(self) -> None:
        #: Given
        path = RootRelativePath.parse('.agents/skills/Review')
        warning = RuleDiagnostic(path, UppercaseEntry(spec=None), Severity.WARNING)
        error = RuleDiagnostic(path, UppercaseEntry(spec=None), Severity.ERROR)

        #: When
        entry = CheckedLayoutEntry(path, diagnostics=(warning, error))

        #: Then
        assert entry.diagnostics == (error, warning), 'a report holds its diagnostics in output order, however built'


@pytest.mark.unit
class TestUndecodableSubject:
    def test_diagnostics_of_an_undecodable_subject_are_invalid_utf8_at_its_path(self) -> None:
        #: Given
        subject = UndecodableSubject(DocumentRef(CorpusName.parse('code'), AspectFilename.parse('latin')), _failure(4))

        #: When
        diagnostics = subject.diagnostics

        #: Then
        assert diagnostics == (
            EngineDiagnostic(RootRelativePath.parse('docs/code/latin.md'), InvalidUtf8(failure=_failure(4))),
        ), "the subject's one diagnostic is the engine's, at the document's path"

    def test_diagnostics_of_an_undecodable_skill_are_invalid_utf8_at_its_skill_file(self) -> None:
        #: Given
        subject = UndecodableSubject(
            SkillRef(ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review')), _failure(4)
        )

        #: When
        diagnostics = subject.diagnostics

        #: Then
        assert diagnostics == (
            EngineDiagnostic(
                RootRelativePath.parse('.agents/skills/review/SKILL.md'), InvalidUtf8(failure=_failure(4))
            ),
        ), "a skill's one diagnostic is the engine's, at its SKILL.md, the file that did not decode"


@pytest.mark.unit
class TestSkippedSubject:
    def test_diagnostics_of_a_skipped_subject_are_none(self) -> None:
        #: Given
        ref = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('a'))
        structure_file = RootRelativePath.parse('docs/__meta__/code.spec.json')
        subject = SkippedSubject(ref, failed_layers=(structure_file,))

        #: When
        diagnostics = subject.diagnostics

        #: Then
        assert diagnostics == (), 'a skipped document is coverage; the failure is reported at its structure file'


@pytest.mark.unit
class TestLoadFailureReport:
    def test_diagnostics_of_a_load_failure_report_are_its_condition_at_its_path(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/__meta__/code.spec.json')
        report = LoadFailureReport(path, MalformedStructureFile(cause=NoRuleStated()))

        #: When
        diagnostics = report.diagnostics

        #: Then
        assert diagnostics == (EngineDiagnostic(path, MalformedStructureFile(cause=NoRuleStated())),), (
            'the failure is one engine diagnostic, filed at the unit that failed'
        )

    def test_severity_of_a_load_failure_diagnostic_is_error(self) -> None:
        #: Given
        report = LoadFailureReport(
            RootRelativePath.parse('docs/__meta__/code.spec.json'), MalformedStructureFile(cause=NoRuleStated())
        )

        #: When
        (diagnostic,) = report.diagnostics

        #: Then
        assert diagnostic.severity is Severity.ERROR, 'no configuration lowers a load failure'
