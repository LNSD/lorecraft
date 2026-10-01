"""Reporting a failure a command cannot recover from: the error, then the errors beneath it."""

import pytest

from lorecraft.core.error import Error

from ..failure import report_failure


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
