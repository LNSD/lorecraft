"""The finding value and its text format: a root-relative path and a one-based line number."""

import pytest

from lorecraft_project.syntax import LineNumber
from lorecraft_vfs import RootRelativePath

from ..reporting import Finding, format_finding


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
