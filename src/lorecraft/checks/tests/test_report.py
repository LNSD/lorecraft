"""The order diagnostics print in: path, primary location, severity, code, then message."""

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.rule import Severity
from lorecraft.rules.tests.sample_rules.rendered_message.long_line import LongLine
from lorecraft.rules.tests.sample_rules.valid.outline.empty_line import EmptyLine
from lorecraft.rules.tests.sample_rules.valid.trailing_space import TrailingSpace
from lorecraft.rules.tests.sample_rules.valid.uppercase_entry import UppercaseEntry

from ..report import Diagnostic, diagnostic_order


@pytest.mark.unit
class TestDiagnosticOrder:
    def test_diagnostic_order_with_paths_differing_compares_them_as_posix_strings(self) -> None:
        #: Given
        occurrence = TrailingSpace(spec=None, line=LineNumber(1))
        nested = Diagnostic(RootRelativePath.parse('a/b.md'), occurrence, Severity.ERROR)
        hyphenated = Diagnostic(RootRelativePath.parse('a-b/c.md'), occurrence, Severity.ERROR)

        #: When
        ordered = sorted([nested, hyphenated], key=diagnostic_order)

        #: Then
        assert ordered == [hyphenated, nested], (
            'a path compares as its string, where `-` is below `/`, not component by component'
        )

    def test_diagnostic_order_with_paths_differing_in_case_puts_uppercase_first(self) -> None:
        #: Given
        occurrence = TrailingSpace(spec=None, line=LineNumber(1))
        lowercase = Diagnostic(RootRelativePath.parse('docs/a.md'), occurrence, Severity.ERROR)
        uppercase = Diagnostic(RootRelativePath.parse('docs/B.md'), occurrence, Severity.ERROR)

        #: When
        ordered = sorted([lowercase, uppercase], key=diagnostic_order)

        #: Then
        assert ordered == [uppercase, lowercase], 'a path compares by code point, never by locale'

    def test_diagnostic_order_with_lines_differing_puts_the_earlier_line_first(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/a.md')
        later = Diagnostic(path, TrailingSpace(spec=None, line=LineNumber(10)), Severity.ERROR)
        earlier = Diagnostic(path, TrailingSpace(spec=None, line=LineNumber(2)), Severity.ERROR)

        #: When
        ordered = sorted([later, earlier], key=diagnostic_order)

        #: Then
        assert ordered == [earlier, later], 'lines compare as numbers, so line 2 is before line 10'

    def test_diagnostic_order_with_the_whole_subject_and_a_line_puts_the_whole_subject_first(self) -> None:
        #: Given
        path = RootRelativePath.parse('skills/a')
        at_line = Diagnostic(path, TrailingSpace(spec=None, line=LineNumber(1)), Severity.ERROR)
        whole_subject = Diagnostic(path, UppercaseEntry(spec=None), Severity.WARNING)

        #: When
        ordered = sorted([at_line, whole_subject], key=diagnostic_order)

        #: Then
        assert ordered == [whole_subject, at_line], (
            'the whole subject is before every line, whatever the severity after it'
        )

    def test_diagnostic_order_with_severities_differing_puts_the_error_first(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/a.md')
        occurrence = TrailingSpace(spec=None, line=LineNumber(1))
        warning = Diagnostic(path, occurrence, Severity.WARNING)
        error = Diagnostic(path, occurrence, Severity.ERROR)

        #: When
        ordered = sorted([warning, error], key=diagnostic_order)

        #: Then
        assert ordered == [error, warning], 'an error is before a warning'

    def test_diagnostic_order_with_codes_differing_compares_them_as_printed(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/a.md')
        second = Diagnostic(path, TrailingSpace(spec=None, line=LineNumber(1)), Severity.ERROR)
        first = Diagnostic(path, EmptyLine(spec=None, line=LineNumber(1)), Severity.ERROR)

        #: When
        ordered = sorted([second, first], key=diagnostic_order)

        #: Then
        assert ordered == [first, second], 'SMP001 is before SMP002'

    def test_diagnostic_order_with_messages_differing_compares_the_message_text(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/a.md')
        ninety = Diagnostic(path, LongLine(spec=None, line=LineNumber(1), length=90), Severity.WARNING)
        eighty_one = Diagnostic(path, LongLine(spec=None, line=LineNumber(1), length=81), Severity.WARNING)

        #: When
        ordered = sorted([ninety, eighty_one], key=diagnostic_order)

        #: Then
        assert ordered == [eighty_one, ninety], 'the message text breaks a tie on every other step'

    def test_diagnostic_order_with_any_input_order_sorts_to_the_same_output(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/a.md')
        long_line = Diagnostic(path, LongLine(spec=None, line=LineNumber(3), length=81), Severity.WARNING)
        trailing_space = Diagnostic(path, TrailingSpace(spec=None, line=LineNumber(3)), Severity.ERROR)
        empty_line = Diagnostic(path, EmptyLine(spec=None, line=LineNumber(3)), Severity.ERROR)
        whole_subject = Diagnostic(path, UppercaseEntry(spec=None), Severity.ERROR)
        next_path = Diagnostic(
            RootRelativePath.parse('docs/b.md'), EmptyLine(spec=None, line=LineNumber(1)), Severity.ERROR
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
