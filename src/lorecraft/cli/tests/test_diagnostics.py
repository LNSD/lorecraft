"""The rules engine's subject reports rendered as text and as JSON, from hand-built reports of real occurrences."""

import json
from pathlib import PurePosixPath
from typing import Final

import pytest
from syrupy.assertion import SnapshotAssertion

from lib.snapshot import TextSnapshotExtension
from lorecraft.checks import (
    CheckedLayoutEntry,
    CheckedSubject,
    RuleDiagnostic,
    SubjectReport,
    UndecodableSubject,
)
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.schemas import DocumentEnd, SectionName
from lorecraft.project.syntax import Heading, LineNumber
from lorecraft.rules.declaration import Severity
from lorecraft.rules.frontmatter.duplicate_key import DuplicateKey
from lorecraft.rules.layout.outside_symlink import OutsideSymlink
from lorecraft.rules.length.too_many_tokens import TooManyTokens
from lorecraft.rules.outline.missing_section import MissingSection
from lorecraft.rules.subject import Facet
from lorecraft.vfs import RootExit, Utf8Failure, Utf8Reason

from ..diagnostic_text import SourceLines, TextStyle, render_text
from ..diagnostics import render_coverage, render_json, render_prefix_summary, render_short, render_summary

_CODE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
_FEAT_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/feat.structure.json')


_PLAIN: Final[TextStyle] = TextStyle(color=False, unicode=True, width=80)


def _sources() -> SourceLines:
    """The lines of the documents of `_every_kind_of_report` that carry a label."""
    return {
        RootRelativePath.parse('docs/code/a.md'): ('---', 'name: a', 'name: b', 'description: x', '---'),
        RootRelativePath.parse('docs/feat/check.md'): ('---', 'name: check', '---', '', '## Options', '', 'Text.'),
    }


def _options_heading() -> Heading:
    """The `Options` section, on line 5, before which the missing `Usage` section belongs."""
    return Heading(level=2, text='Options', line=_line(5), empty=False, words=3)


def _document(corpus: str, filename: str) -> DocumentRef:
    return DocumentRef(CorpusName.parse(corpus), AspectFilename.parse(filename))


def _line(number: int) -> LineNumber:
    return LineNumber.from_int(number)


def _latin_failure() -> Utf8Failure:
    return Utf8Failure(
        line=4,
        offset=31,
        invalid=b'\xe9',
        reason=Utf8Reason.INVALID_CONTINUATION_BYTE,
    )


def _every_kind_of_report() -> tuple[SubjectReport, ...]:
    """One report of each kind, handed over out of path order, so the output order is the renderer's own.

    - `docs/feat/check.md` lacks a section, with a multi-line example, and is ungoverned for two facets.
    - `.agents/skills/review` is a symlink leading out of the repository: a layout entry, at the whole subject.
    - `docs/code/latin.md` did not decode.
    - `docs/code/a.md` repeats a key, with a label, and exceeds its budget at warning severity.
    - `docs/arch/adr.md` holds no diagnostic and is ungoverned for its structure.
    """
    check = _document('feat', 'check')
    missing_usage = MissingSection(
        spec=_FEAT_SPEC,
        line=_line(5),
        section=SectionName.parse('Usage'),
        before=_options_heading(),
        description='How to invoke the command.',
        example='Run `lorecraft check` from the repository root:\n\n```console\n$ lorecraft check\n```',
    )
    review = RootRelativePath.parse('.agents/skills/review')
    outside = OutsideSymlink(leaves_at=RootExit(review, PurePosixPath('/home/alex/review')))
    a = _document('code', 'a')
    duplicate_name = DuplicateKey(spec=_CODE_SPEC, line=_line(3), key='name', first_line=_line(2), kept_line=_line(3))
    over_budget = TooManyTokens(spec=_CODE_SPEC, line=_line(1), token_count=2400, budget=2000)
    return (
        CheckedSubject(
            check,
            diagnostics=(RuleDiagnostic(check.path, missing_usage, Severity.ERROR),),
            ungoverned=(Facet.FRONTMATTER, Facet.BUDGET),
        ),
        CheckedLayoutEntry(review, diagnostics=(RuleDiagnostic(review, outside, Severity.ERROR),)),
        UndecodableSubject(_document('code', 'latin'), _latin_failure()),
        CheckedSubject(
            a,
            diagnostics=(
                RuleDiagnostic(a.path, duplicate_name, Severity.ERROR),
                RuleDiagnostic(a.path, over_budget, Severity.WARNING),
            ),
            ungoverned=(),
        ),
        CheckedSubject(_document('arch', 'adr'), diagnostics=(), ungoverned=(Facet.STRUCTURE,)),
    )


@pytest.mark.unit
class TestRenderText:
    def test_render_text_with_every_kind_of_report_matches_the_snapshot(self, snapshot: SnapshotAssertion) -> None:
        #: Given
        reports = _every_kind_of_report()
        expected = snapshot.use_extension(TextSnapshotExtension)

        #: When
        text = render_text(reports, _sources(), _PLAIN)

        #: Then
        assert text == expected, 'the diagnostics of every kind of report match the reviewed snapshot'

    def test_render_text_with_no_report_prints_nothing(self) -> None:
        #: Given
        reports: tuple[SubjectReport, ...] = ()

        #: When
        text = render_text(reports, {}, _PLAIN)

        #: Then
        assert text == '', 'an empty run has no diagnostic to print'

    def test_render_text_without_unicode_draws_the_gutter_and_underlines_in_ascii(self) -> None:
        #: Given
        reports = _every_kind_of_report()
        style = TextStyle(color=False, unicode=False, width=80)

        #: When
        text = render_text(reports, _sources(), style)

        #: Then
        assert ('2 | name: a\n  | ------- first written here\n3 | name: b\n  | ^^^^^^^ written again here') in text, (
            'the secondary label is underlined with dashes and the primary one with carets'
        )
        assert '│' not in text and '─' not in text and '┄' not in text, 'no box-drawing character is left'

    def test_render_text_with_colour_emphasises_the_severity_and_the_location(self) -> None:
        #: Given
        reports = _every_kind_of_report()
        style = TextStyle(color=True, unicode=True, width=80)

        #: When
        text = render_text(reports, _sources(), style)

        #: Then
        assert '\x1b[31m\x1b[1merror[FM005]\x1b[0m' in text, 'an error is bold red'
        assert '\x1b[33m\x1b[1mwarning[LEN001]\x1b[0m' in text, 'a warning is bold yellow'
        assert '\x1b[34m\x1b[1m-->\x1b[0m' in text, 'the location arrow is bold blue'

    def test_render_text_without_the_source_of_a_label_prints_it_as_an_at_line(self) -> None:
        #: Given
        reports = _every_kind_of_report()

        #: When
        text = render_text(reports, {}, _PLAIN)

        #: Then
        assert '  = at docs/code/a.md:3: written again here' in text, 'the label stays, without an excerpt'
        assert '3 │' not in text, 'no source line is excerpted'

    def test_render_text_with_a_long_note_wraps_it_under_its_first_line(self) -> None:
        #: Given
        reports = _every_kind_of_report()
        style = TextStyle(color=False, unicode=True, width=60)

        #: When
        text = render_text(reports, _sources(), style)

        #: Then
        assert (
            '  = help: split the document, or move what an agent needs\n'
            '          only some of the time into a document of its own\n'
            '          and link to it'
        ) in text, 'the help wraps at the width and its continuation lines align under its text'

    def test_render_text_with_a_long_sample_line_leaves_it_unwrapped(self) -> None:
        #: Given
        guide = _document('feat', 'guide')
        sample_line = (
            '- an item of a list whose text runs well past the width of the terminal it is drawn to, and wraps'
        )
        missing_usage = MissingSection(
            spec=_FEAT_SPEC,
            line=_line(9),
            section=SectionName.parse('Usage'),
            before=DocumentEnd(last_line=_line(9), after=None),
            description=None,
            example=f'{sample_line}\n  - and a nested one',
        )
        reports: tuple[SubjectReport, ...] = (
            CheckedSubject(
                guide, diagnostics=(RuleDiagnostic(guide.path, missing_usage, Severity.ERROR),), ungoverned=()
            ),
        )
        style = TextStyle(color=False, unicode=True, width=60)

        #: When
        text = render_text(reports, {}, style)

        #: Then
        assert f'          {sample_line}\n' in text, 'a line of a sample is drawn whole, however wide the terminal'
        assert '            - and a nested one' in text, 'the hanging indent of the sample survives'

    def test_render_text_with_a_note_of_padded_and_blank_lines_aligns_and_strips_them(self) -> None:
        #: Given
        guide = _document('feat', 'guide')
        # the example's first line ends in spaces, its second holds only spaces, and its third is indented
        missing_usage = MissingSection(
            spec=_FEAT_SPEC,
            line=_line(9),
            section=SectionName.parse('Usage'),
            before=DocumentEnd(last_line=_line(9), after=None),
            description=None,
            example='Run it:  \n   \n    lorecraft check\n',
        )
        reports: tuple[SubjectReport, ...] = (
            CheckedSubject(
                guide, diagnostics=(RuleDiagnostic(guide.path, missing_usage, Severity.ERROR),), ungoverned=()
            ),
        )

        #: When
        text = render_text(reports, {}, _PLAIN)

        #: Then
        assert text == (
            'error[OUT006]: missing required section `Usage`\n'
            ' --> docs/feat/guide.md:9\n'
            '  = at docs/feat/guide.md:9: expected `Usage` before the end of the document\n'
            ' ::: docs/__meta__/feat.structure.json\n'
            '  │\n'
            '  = note: the document structure is set here\n'
            '  = note: for example:\n'
            '          ## Usage\n'
            '\n'
            '          Run it:\n'
            '\n'
            '              lorecraft check'
        ), 'later lines align under the first, keep their indentation, and lose trailing whitespace'

    def test_render_text_with_a_note_of_crlf_lines_leaves_no_carriage_return(self) -> None:
        #: Given
        guide = _document('feat', 'guide')
        missing_usage = MissingSection(
            spec=_FEAT_SPEC,
            line=_line(9),
            section=SectionName.parse('Usage'),
            before=DocumentEnd(last_line=_line(9), after=None),
            description=None,
            example='Run it:\r\n    lorecraft check',
        )
        reports: tuple[SubjectReport, ...] = (
            CheckedSubject(
                guide, diagnostics=(RuleDiagnostic(guide.path, missing_usage, Severity.ERROR),), ungoverned=()
            ),
        )

        #: When
        text = render_text(reports, {}, _PLAIN)

        #: Then
        assert '\r' not in text, 'a CRLF line break in a note prints as a plain line break'
        assert '          Run it:\n              lorecraft check' in text, (
            'the lines after the break keep their indentation under the note'
        )


@pytest.mark.unit
class TestRenderShort:
    def test_render_short_with_every_kind_of_report_prints_one_line_per_diagnostic(self) -> None:
        #: Given
        reports = _every_kind_of_report()

        #: When
        text = render_short(reports)

        #: Then
        assert text == (
            '.agents/skills/review: error[LAY001]: symlink leads outside the repository\n'
            'docs/code/a.md:1: warning[LEN001]: too many tokens (2400 > 2000)\n'
            "docs/code/a.md:3: error[FM005]: duplicate key 'name'\n"
            'docs/code/latin.md:4: error[LC001]: file is not valid UTF-8\n'
            'docs/feat/check.md:5: error[OUT006]: missing required section `Usage`'
        ), 'a line holds the place, the severity, the code and the message, and the layout entry has no line'

    def test_render_short_with_no_report_prints_nothing(self) -> None:
        #: Given
        reports: tuple[SubjectReport, ...] = ()

        #: When
        text = render_short(reports)

        #: Then
        assert text == '', 'an empty run has no diagnostic to print'


@pytest.mark.unit
class TestRenderCoverage:
    def test_render_coverage_with_every_kind_of_report_matches_the_snapshot(self, snapshot: SnapshotAssertion) -> None:
        #: Given
        reports = _every_kind_of_report()
        expected = snapshot.use_extension(TextSnapshotExtension)

        #: When
        text = render_coverage(reports)

        #: Then
        assert text == expected, 'the ungoverned subjects match the reviewed snapshot, in path order'

    def test_render_coverage_with_every_subject_governed_prints_nothing(self) -> None:
        #: Given
        a = _document('code', 'a')
        reports: tuple[SubjectReport, ...] = (
            CheckedSubject(a, diagnostics=(), ungoverned=()),
            UndecodableSubject(_document('code', 'latin'), _latin_failure()),
        )

        #: When
        text = render_coverage(reports)

        #: Then
        assert text == '', 'a run whose subjects are all governed has no coverage line'


@pytest.mark.unit
class TestRenderSummary:
    def test_render_summary_with_every_kind_of_report_counts_subjects_errors_and_warnings(self) -> None:
        #: Given
        reports = _every_kind_of_report()

        #: When
        text = render_summary(reports)

        #: Then
        assert text == 'checked 5 subject(s): 4 error(s), 1 warning(s)', (
            'every report is a subject, and the undecodable one counts as an error through its severity'
        )

    def test_render_summary_with_no_report_counts_nothing(self) -> None:
        #: Given
        reports: tuple[SubjectReport, ...] = ()

        #: When
        text = render_summary(reports)

        #: Then
        assert text == 'checked 0 subject(s): 0 error(s), 0 warning(s)', 'an empty run still prints its summary'


@pytest.mark.unit
class TestRenderPrefixSummary:
    def test_render_prefix_summary_with_every_kind_of_report_counts_each_prefix(self) -> None:
        #: Given
        reports = _every_kind_of_report()

        #: When
        text = render_prefix_summary(reports)

        #: Then
        assert text == ('FM   1 error\nLAY  1 error\nLC   1 error\nLEN  1 warning\nOUT  1 error'), (
            'each prefix is listed in order with its errors and warnings, each singular for one'
        )

    def test_render_prefix_summary_with_no_report_prints_nothing(self) -> None:
        #: Given
        reports: tuple[SubjectReport, ...] = ()

        #: When
        text = render_prefix_summary(reports)

        #: Then
        assert text == '', 'an empty run has no prefix to count'


@pytest.mark.unit
class TestRenderJson:
    def test_render_json_with_every_kind_of_report_prints_one_compact_line(self) -> None:
        #: Given
        reports = _every_kind_of_report()

        #: When
        text = render_json(reports)

        #: Then
        assert text == json.dumps(json.loads(text), separators=(',', ':'), ensure_ascii=False), (
            'the document holds no indentation, no line break and no blank after a separator'
        )

    def test_render_json_with_a_non_ascii_key_writes_it_as_utf8(self) -> None:
        #: Given
        a = _document('code', 'a')
        duplicate_key = DuplicateKey(
            spec=_CODE_SPEC, line=_line(3), key='nom é', first_line=_line(2), kept_line=_line(3)
        )
        reports: tuple[SubjectReport, ...] = (
            CheckedSubject(a, diagnostics=(RuleDiagnostic(a.path, duplicate_key, Severity.ERROR),), ungoverned=()),
        )

        #: When
        text = render_json(reports)

        #: Then
        assert 'nom é' in text, 'a non-ASCII character is written as it is, not as a \\u escape'

    def test_render_json_with_every_kind_of_report_encodes_the_whole_run(self) -> None:
        #: Given
        reports = _every_kind_of_report()
        expected = {
            'diagnostics': [
                {
                    'path': '.agents/skills/review',
                    'line': None,
                    'severity': 'error',
                    'code': 'LAY001',
                    'name': 'outside-symlink',
                    'message': 'symlink leads outside the repository',
                    'labels': [],
                    'children': [
                        {
                            'kind': 'help',
                            'text': (
                                'an absolute target resolves differently in every checkout; '
                                'move what it links to into the repository'
                            ),
                            'path': None,
                            'line': None,
                        },
                        {
                            'kind': 'note',
                            'text': 'leaves the repository at .agents/skills/review -> /home/alex/review',
                            'path': None,
                            'line': None,
                        },
                    ],
                },
                {
                    'path': 'docs/code/a.md',
                    'line': 1,
                    'severity': 'warning',
                    'code': 'LEN001',
                    'name': 'too-many-tokens',
                    'message': 'too many tokens (2400 > 2000)',
                    'labels': [{'path': 'docs/code/a.md', 'line': 1, 'text': 'tokens over the budget: 400'}],
                    'children': [
                        {
                            'kind': 'note',
                            'text': 'the limit is set here',
                            'path': 'docs/__meta__/code.structure.json',
                            'line': None,
                        },
                        {
                            'kind': 'help',
                            'text': (
                                'split the document, or move what an agent needs only some of the time into a '
                                'document of its own and link to it'
                            ),
                            'path': None,
                            'line': None,
                        },
                        {
                            'kind': 'note',
                            'text': (
                                'tokens are counted as o200k_base over the whole file: frontmatter, code blocks and '
                                'tables included'
                            ),
                            'path': None,
                            'line': None,
                        },
                    ],
                },
                {
                    'path': 'docs/code/a.md',
                    'line': 3,
                    'severity': 'error',
                    'code': 'FM005',
                    'name': 'duplicate-key',
                    'message': "duplicate key 'name'",
                    'labels': [
                        {'path': 'docs/code/a.md', 'line': 3, 'text': 'written again here'},
                        {'path': 'docs/code/a.md', 'line': 2, 'text': 'first written here'},
                    ],
                    'children': [
                        {
                            'kind': 'note',
                            'text': 'the frontmatter schema is set here',
                            'path': 'docs/__meta__/code.structure.json',
                            'line': None,
                        },
                        {'kind': 'help', 'text': "write 'name' once, with the value meant", 'path': None, 'line': None},
                    ],
                },
                {
                    'path': 'docs/code/latin.md',
                    'line': 4,
                    'severity': 'error',
                    'code': 'LC001',
                    'name': 'invalid-utf8',
                    'message': 'file is not valid UTF-8',
                    'labels': [
                        {
                            'path': 'docs/code/latin.md',
                            'line': 4,
                            'text': '0xE9 at byte offset 31 starts a character the next byte does not continue',
                        }
                    ],
                    'children': [{'kind': 'help', 'text': 'save the file as UTF-8', 'path': None, 'line': None}],
                },
                {
                    'path': 'docs/feat/check.md',
                    'line': 5,
                    'severity': 'error',
                    'code': 'OUT006',
                    'name': 'missing-section',
                    'message': 'missing required section `Usage`',
                    'labels': [{'path': 'docs/feat/check.md', 'line': 5, 'text': 'expected `Usage` before `Options`'}],
                    'children': [
                        {
                            'kind': 'note',
                            'text': 'the document structure is set here',
                            'path': 'docs/__meta__/feat.structure.json',
                            'line': None,
                        },
                        {'kind': 'help', 'text': 'How to invoke the command.', 'path': None, 'line': None},
                        {
                            'kind': 'note',
                            'text': (
                                'for example:\n## Usage\n\nRun `lorecraft check` from the repository root:\n\n'
                                '```console\n$ lorecraft check\n```'
                            ),
                            'path': None,
                            'line': None,
                        },
                    ],
                },
            ],
            'summary': {'subjects': 5, 'errors': 4, 'warnings': 1},
            'coverage': [
                {'path': 'docs/arch/adr.md', 'ungoverned': ['structure']},
                {'path': 'docs/feat/check.md', 'ungoverned': ['frontmatter', 'budget']},
            ],
        }

        #: When
        text = render_json(reports)

        #: Then
        assert json.loads(text) == expected, (
            'the document holds every diagnostic in output order, the summary, and the coverage in path order'
        )

    def test_render_json_with_no_report_encodes_every_key_empty(self) -> None:
        #: Given
        reports: tuple[SubjectReport, ...] = ()

        #: When
        text = render_json(reports)

        #: Then
        assert json.loads(text) == {
            'diagnostics': [],
            'summary': {'subjects': 0, 'errors': 0, 'warnings': 0},
            'coverage': [],
        }, 'an empty run still writes every key'
