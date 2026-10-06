"""The order diagnostics print in, an engine diagnostic's severity, and the diagnostics each subject report holds."""

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.skill import SkillRef
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import Severity
from lorecraft.rules.engine.invalid_utf8 import InvalidUtf8
from lorecraft.rules.tests.sample_rules.rendered_message.long_line import LongLine
from lorecraft.rules.tests.sample_rules.token_count.sample_condition import SampleCondition
from lorecraft.rules.tests.sample_rules.valid.outline.empty_line import EmptyLine
from lorecraft.rules.tests.sample_rules.valid.trailing_space import TrailingSpace
from lorecraft.rules.tests.sample_rules.valid.uppercase_entry import UppercaseEntry

from ..report import (
    CheckedLayoutEntry,
    CheckedSubject,
    EngineDiagnostic,
    RuleDiagnostic,
    UndecodableSubject,
    diagnostic_order,
)


@pytest.mark.unit
class TestDiagnosticOrder:
    def test_diagnostic_order_with_paths_differing_compares_them_as_posix_strings(self) -> None:
        #: Given
        occurrence = TrailingSpace(spec=None, line=LineNumber.from_int(1))
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
        occurrence = TrailingSpace(spec=None, line=LineNumber.from_int(1))
        lowercase = RuleDiagnostic(RootRelativePath.parse('docs/a.md'), occurrence, Severity.ERROR)
        uppercase = RuleDiagnostic(RootRelativePath.parse('docs/B.md'), occurrence, Severity.ERROR)

        #: When
        ordered = sorted([lowercase, uppercase], key=diagnostic_order)

        #: Then
        assert ordered == [uppercase, lowercase], 'a path compares by code point, never by locale'

    def test_diagnostic_order_with_lines_differing_puts_the_earlier_line_first(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/a.md')
        later = RuleDiagnostic(path, TrailingSpace(spec=None, line=LineNumber.from_int(10)), Severity.ERROR)
        earlier = RuleDiagnostic(path, TrailingSpace(spec=None, line=LineNumber.from_int(2)), Severity.ERROR)

        #: When
        ordered = sorted([later, earlier], key=diagnostic_order)

        #: Then
        assert ordered == [earlier, later], 'lines compare as numbers, so line 2 is before line 10'

    def test_diagnostic_order_with_the_whole_subject_and_a_line_puts_the_whole_subject_first(self) -> None:
        #: Given
        path = RootRelativePath.parse('skills/a')
        at_line = RuleDiagnostic(path, TrailingSpace(spec=None, line=LineNumber.from_int(1)), Severity.ERROR)
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
        occurrence = TrailingSpace(spec=None, line=LineNumber.from_int(1))
        warning = RuleDiagnostic(path, occurrence, Severity.WARNING)
        error = RuleDiagnostic(path, occurrence, Severity.ERROR)

        #: When
        ordered = sorted([warning, error], key=diagnostic_order)

        #: Then
        assert ordered == [error, warning], 'an error is before a warning'

    def test_diagnostic_order_with_codes_differing_compares_them_as_printed(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/a.md')
        second = RuleDiagnostic(path, TrailingSpace(spec=None, line=LineNumber.from_int(1)), Severity.ERROR)
        first = RuleDiagnostic(path, EmptyLine(spec=None, line=LineNumber.from_int(1)), Severity.ERROR)

        #: When
        ordered = sorted([second, first], key=diagnostic_order)

        #: Then
        assert ordered == [first, second], 'SMP001 is before SMP002'

    def test_diagnostic_order_with_messages_differing_compares_the_message_text(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/a.md')
        ninety = RuleDiagnostic(path, LongLine(spec=None, line=LineNumber.from_int(1), length=90), Severity.WARNING)
        eighty_one = RuleDiagnostic(path, LongLine(spec=None, line=LineNumber.from_int(1), length=81), Severity.WARNING)

        #: When
        ordered = sorted([ninety, eighty_one], key=diagnostic_order)

        #: Then
        assert ordered == [eighty_one, ninety], 'the message text breaks a tie on every other step'

    def test_diagnostic_order_with_any_input_order_sorts_to_the_same_output(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/a.md')
        long_line = RuleDiagnostic(path, LongLine(spec=None, line=LineNumber.from_int(3), length=81), Severity.WARNING)
        trailing_space = RuleDiagnostic(path, TrailingSpace(spec=None, line=LineNumber.from_int(3)), Severity.ERROR)
        empty_line = RuleDiagnostic(path, EmptyLine(spec=None, line=LineNumber.from_int(3)), Severity.ERROR)
        whole_subject = RuleDiagnostic(path, UppercaseEntry(spec=None), Severity.ERROR)
        next_path = RuleDiagnostic(
            RootRelativePath.parse('docs/b.md'), EmptyLine(spec=None, line=LineNumber.from_int(1)), Severity.ERROR
        )
        diagnostics = [long_line, trailing_space, empty_line, whole_subject, next_path]

        #: When
        forward = sorted(diagnostics, key=diagnostic_order)
        backward = sorted(reversed(diagnostics), key=diagnostic_order)

        #: Then
        assert forward == [whole_subject, empty_line, trailing_space, long_line, next_path], (
            'the diagnostics sort by path, location, severity and code'
        )
        assert backward == forward, 'the order is total, so the input order never shows in the output'

    def test_diagnostic_order_with_an_engine_condition_and_a_rule_puts_the_whole_subject_first(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/code/a.md')
        at_line = RuleDiagnostic(path, TrailingSpace(spec=None, line=LineNumber.from_int(1)), Severity.ERROR)
        condition = EngineDiagnostic(path, InvalidUtf8())

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
class TestCheckedSubject:
    def test_checked_subject_with_diagnostics_out_of_order_holds_them_in_diagnostic_order(self) -> None:
        #: Given
        ref = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('a'))
        later = RuleDiagnostic(ref.path, TrailingSpace(spec=None, line=LineNumber.from_int(10)), Severity.ERROR)
        earlier = RuleDiagnostic(ref.path, TrailingSpace(spec=None, line=LineNumber.from_int(2)), Severity.ERROR)

        #: When
        subject = CheckedSubject(ref, diagnostics=(later, earlier), ungoverned=())

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
        subject = UndecodableSubject(DocumentRef(CorpusName.parse('code'), AspectFilename.parse('latin')))

        #: When
        diagnostics = subject.diagnostics

        #: Then
        assert diagnostics == (EngineDiagnostic(RootRelativePath.parse('docs/code/latin.md'), InvalidUtf8()),), (
            "the subject's one diagnostic is the engine's, at the document's path"
        )

    def test_diagnostics_of_an_undecodable_skill_are_invalid_utf8_at_its_skill_file(self) -> None:
        #: Given
        subject = UndecodableSubject(SkillRef(RootRelativePath.parse('.agents/skills/review')))

        #: When
        diagnostics = subject.diagnostics

        #: Then
        assert diagnostics == (
            EngineDiagnostic(RootRelativePath.parse('.agents/skills/review/SKILL.md'), InvalidUtf8()),
        ), "a skill's one diagnostic is the engine's, at its SKILL.md, the file that did not decode"
