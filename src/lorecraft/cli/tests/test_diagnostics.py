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
from lorecraft.vfs import RootExit

from ..diagnostics import render_coverage, render_diagnostics, render_json, render_summary

_CODE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
_FEAT_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/feat.structure.json')


def _options_heading() -> Heading:
    """The `Options` section, on line 5, before which the missing `Usage` section belongs."""
    return Heading(level=2, text='Options', line=_line(5), empty=False, words=3)


def _document(corpus: str, filename: str) -> DocumentRef:
    return DocumentRef(CorpusName.parse(corpus), AspectFilename.parse(filename))


def _line(number: int) -> LineNumber:
    return LineNumber.from_int(number)


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
        UndecodableSubject(_document('code', 'latin')),
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
class TestRenderDiagnostics:
    def test_render_diagnostics_with_every_kind_of_report_matches_the_snapshot(
        self, snapshot: SnapshotAssertion
    ) -> None:
        #: Given
        reports = _every_kind_of_report()
        expected = snapshot.use_extension(TextSnapshotExtension)

        #: When
        text = render_diagnostics(reports)

        #: Then
        assert text == expected, 'the diagnostics of every kind of report match the reviewed snapshot'

    def test_render_diagnostics_with_no_report_prints_nothing(self) -> None:
        #: Given
        reports: tuple[SubjectReport, ...] = ()

        #: When
        text = render_diagnostics(reports)

        #: Then
        assert text == '', 'an empty run has no diagnostic to print'

    def test_render_diagnostics_with_a_note_of_padded_and_blank_lines_aligns_and_strips_them(self) -> None:
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
        text = render_diagnostics(reports)

        #: Then
        assert text == (
            'docs/feat/guide.md:9: error[OUT006]: missing required section `Usage`\n'
            '  --> docs/feat/guide.md:9: expected `Usage` before the end of the document\n'
            '  = note: the document structure is set here (docs/__meta__/feat.structure.json)\n'
            '  = note: for example:\n'
            '          ## Usage\n'
            '\n'
            '          Run it:\n'
            '\n'
            '              lorecraft check'
        ), 'later lines align under the first, keep their indentation, and lose trailing whitespace'

    def test_render_diagnostics_with_a_note_of_crlf_lines_leaves_no_carriage_return(self) -> None:
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
        text = render_diagnostics(reports)

        #: Then
        assert text == (
            'docs/feat/guide.md:9: error[OUT006]: missing required section `Usage`\n'
            '  --> docs/feat/guide.md:9: expected `Usage` before the end of the document\n'
            '  = note: the document structure is set here (docs/__meta__/feat.structure.json)\n'
            '  = note: for example:\n'
            '          ## Usage\n'
            '\n'
            '          Run it:\n'
            '              lorecraft check'
        ), 'a CRLF line break in a note prints as a plain line break'


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
            UndecodableSubject(_document('code', 'latin')),
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
class TestRenderJson:
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
                            'kind': 'note',
                            'text': 'leaves the repository at .agents/skills/review -> /home/alex/review',
                            'path': None,
                            'line': None,
                        },
                        {
                            'kind': 'help',
                            'text': 'keep every file a skill loads inside the repository',
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
                    'labels': [],
                    'children': [
                        {
                            'kind': 'note',
                            'text': 'the budget is set here',
                            'path': 'docs/__meta__/code.structure.json',
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
                    'line': None,
                    'severity': 'error',
                    'code': 'LC001',
                    'name': 'invalid-utf8',
                    'message': 'file is not valid UTF-8',
                    'labels': [],
                    'children': [],
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
