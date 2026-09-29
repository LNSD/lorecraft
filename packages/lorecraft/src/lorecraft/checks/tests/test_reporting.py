"""The finding value, located from a violation, and its text format: a root-relative path and a one-based line."""

import pytest

from lorecraft_project.syntax import LineNumber
from lorecraft_vfs import RootRelativePath

from ..reporting import Finding, Violation, format_finding


@pytest.mark.unit
class TestFormatFinding:
    def test_format_finding_with_a_path_and_line_prints_path_colon_line(self) -> None:
        #: Given
        finding = Finding(
            path=RootRelativePath.parse('docs/code/guide.md'),
            line=LineNumber(3),
            rule='frontmatter.name-matches-filename',
            message='`name` is wrong',
        )

        #: When
        text = format_finding(finding)

        #: Then
        assert text == 'docs/code/guide.md:3: [frontmatter.name-matches-filename] `name` is wrong', (
            f'a finding prints as path:line: [rule] message, got {text!r}'
        )


@pytest.mark.unit
class TestFindingAt:
    def test_finding_at_a_path_keeps_the_violation_and_adds_the_path(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/code/guide.md')
        violation = Violation(line=LineNumber(3), rule='structure.outline', message='missing section')

        #: When
        finding = Finding.at(path, violation)

        #: Then
        assert finding == Finding(path=path, line=LineNumber(3), rule='structure.outline', message='missing section'), (
            'a finding is the violation, located in the document at the path'
        )
