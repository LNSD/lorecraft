"""The finding value, located from a violation, and its text format: a root-relative path and a one-based line."""

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber

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
        spec = RootRelativePath.parse('docs/__meta__/code.structure.json')
        violation = Violation(line=LineNumber(3), rule='structure.outline', message='missing section', spec=spec)

        #: When
        finding = Finding.at(path, violation)

        #: Then
        assert finding == Finding(
            path=path, line=LineNumber(3), rule='structure.outline', message='missing section', spec=spec
        ), 'a finding is the violation, spec included, located in the document at the path'
