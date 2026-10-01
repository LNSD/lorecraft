"""The finding value, located from a violation, and its text format: a root-relative path and a one-based line."""

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber

from ..reporting import Finding, Note, NoteKind, Violation, format_finding


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

    def test_format_finding_with_a_help_note_prints_it_under_the_message(self) -> None:
        #: Given
        finding = Finding(
            path=RootRelativePath.parse('docs/feat/x.md'),
            line=LineNumber(1),
            rule='structure.outline',
            message='missing required section `Key Concepts`',
            notes=(Note(NoteKind.HELP, 'The terms a reader needs before the rest of the document.'),),
        )

        #: When
        text = format_finding(finding)

        #: Then
        assert text == (
            'docs/feat/x.md:1: [structure.outline] missing required section `Key Concepts`\n'
            '  = help: The terms a reader needs before the rest of the document.'
        ), f'a note prints on its own line, labelled with its kind, got {text!r}'

    def test_format_finding_with_a_multi_line_note_aligns_its_later_lines_under_its_first(self) -> None:
        #: Given
        finding = Finding(
            path=RootRelativePath.parse('docs/feat/x.md'),
            line=LineNumber(1),
            rule='structure.outline',
            message='missing required section `Key Concepts`',
            notes=(Note(NoteKind.NOTE, 'for example:\n## Key Concepts'),),
        )

        #: When
        text = format_finding(finding)

        #: Then
        assert text == (
            'docs/feat/x.md:1: [structure.outline] missing required section `Key Concepts`\n'
            '  = note: for example:\n'
            '          ## Key Concepts'
        ), f'every later line of a note starts under its first, got {text!r}'

    def test_format_finding_with_a_blank_line_in_a_note_prints_it_empty(self) -> None:
        #: Given
        finding = Finding(
            path=RootRelativePath.parse('docs/feat/x.md'),
            line=LineNumber(1),
            rule='structure.outline',
            message='missing required section `Key Concepts`',
            notes=(Note(NoteKind.NOTE, 'first\n\nthird'),),
        )

        #: When
        text = format_finding(finding)

        #: Then
        assert text == (
            'docs/feat/x.md:1: [structure.outline] missing required section `Key Concepts`\n'
            '  = note: first\n'
            '\n'
            '          third'
        ), f'a blank line in a note carries no whitespace, got {text!r}'

    def test_format_finding_with_a_note_ending_in_a_line_break_adds_no_blank_line(self) -> None:
        #: Given
        finding = Finding(
            path=RootRelativePath.parse('docs/feat/x.md'),
            line=LineNumber(1),
            rule='structure.outline',
            message='missing required section `Key Concepts`',
            notes=(Note(NoteKind.NOTE, 'first\nsecond\n'),),
        )

        #: When
        text = format_finding(finding)

        #: Then
        assert text == (
            'docs/feat/x.md:1: [structure.outline] missing required section `Key Concepts`\n'
            '  = note: first\n'
            '          second'
        ), f'a trailing line break in a note prints no empty last line, got {text!r}'

    def test_format_finding_with_a_crlf_note_leaves_no_carriage_return(self) -> None:
        #: Given
        finding = Finding(
            path=RootRelativePath.parse('docs/feat/x.md'),
            line=LineNumber(1),
            rule='structure.outline',
            message='missing required section `Key Concepts`',
            notes=(Note(NoteKind.NOTE, 'first\r\nsecond'),),
        )

        #: When
        text = format_finding(finding)

        #: Then
        assert text == (
            'docs/feat/x.md:1: [structure.outline] missing required section `Key Concepts`\n'
            '  = note: first\n'
            '          second'
        ), f'a CRLF line break in a note prints as a plain line break, got {text!r}'

    def test_format_finding_with_a_whitespace_only_line_in_a_note_prints_it_empty(self) -> None:
        #: Given
        finding = Finding(
            path=RootRelativePath.parse('docs/feat/x.md'),
            line=LineNumber(1),
            rule='structure.outline',
            message='missing required section `Key Concepts`',
            notes=(Note(NoteKind.NOTE, 'first\n   \nthird'),),
        )

        #: When
        text = format_finding(finding)

        #: Then
        assert text == (
            'docs/feat/x.md:1: [structure.outline] missing required section `Key Concepts`\n'
            '  = note: first\n'
            '\n'
            '          third'
        ), f'a whitespace-only line in a note prints empty, got {text!r}'


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

    def test_finding_at_a_path_with_a_violation_carrying_notes_keeps_them_in_order(self) -> None:
        #: Given
        path = RootRelativePath.parse('docs/code/guide.md')
        notes = (Note(NoteKind.HELP, 'what the section holds'), Note(NoteKind.NOTE, 'for example:\n## Checklist'))
        violation = Violation(line=LineNumber(1), rule='structure.outline', message='missing section', notes=notes)

        #: When
        finding = Finding.at(path, violation)

        #: Then
        assert finding.notes == notes, f"a finding carries its violation's notes unchanged, got {finding.notes!r}"
