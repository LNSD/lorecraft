"""The rules engine's subject reports rendered as text and as JSON, from hand-built reports of real occurrences."""

import json
from pathlib import PurePosixPath
from typing import Final

import pytest
from syrupy.assertion import SnapshotAssertion

from lib.overruns import overrun
from lib.snapshot import TextSnapshotExtension
from lorecraft.core.lines import ByteOffset, Line
from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.item import ItemRef
from lorecraft.project.schemas import DocumentEnd, DocumentFrontmatterOwner, SectionName
from lorecraft.project.skill import OutsideSymlinkRef
from lorecraft.project.syntax import LineNumber, SectionHeading, WordCount
from lorecraft.rules.engine.malformed_structure_file import FormatViolated, MalformedStructureFile
from lorecraft.rules.frontmatter.duplicate_key import DuplicateKey
from lorecraft.rules.identity import Level
from lorecraft.rules.layout.escaping_symlink import EscapingSymlink
from lorecraft.rules.length.too_many_tokens import TooManyTokens
from lorecraft.rules.level_resolution import DefaultLevel, ElevatedWarning, OverriddenLevel, WrittenSelector
from lorecraft.rules.outline.missing_section import MissingSection
from lorecraft.rules.report import (
    BlockedSubject,
    CheckedItem,
    CheckedLayoutEntry,
    LoadFailureReport,
    RefusedSubject,
    RuleDiagnostic,
    RunReport,
    UncheckedSymlink,
    UndecodableSubject,
)
from lorecraft.rules.subject import SpecPart
from lorecraft.rules.tests.level_helpers import default_level
from lorecraft.vfs import (
    AbsoluteSymlinkTarget,
    RelativeSymlinkTarget,
    ResolvedPath,
    RootExit,
    SymlinkTarget,
    Utf8Failure,
    Utf8Reason,
)

from ..diagnostic_text import SourceLines, SourceText, TextStyle, render_text
from ..diagnostics import render_coverage, render_json, render_prefix_summary, render_short, render_summary

_CODE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.spec.json')
_FEAT_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/feat.spec.json')
_CODE_OWNER: Final[DocumentFrontmatterOwner] = DocumentFrontmatterOwner(
    filename=AspectFilename.parse('guide'), spec=_CODE_SPEC
)


_PLAIN: Final[TextStyle] = TextStyle(color=False, unicode=True, width=80)


def _target(raw: str) -> SymlinkTarget:
    """Wrap a target written as it would be by `os.readlink`."""
    target = PurePosixPath(raw)
    if target.is_absolute():
        return AbsoluteSymlinkTarget(target)
    return RelativeSymlinkTarget(target)


def _sources() -> SourceLines:
    """The lines of the documents of `_every_kind_of_report` that carry a label."""
    return {
        RootRelativePath.parse('docs/code/a.md'): SourceText(('---', 'name: a', 'name: b', 'description: x', '---')),
        RootRelativePath.parse('docs/feat/check.md'): SourceText(
            ('---', 'name: check', '---', '', '## Options', '', 'Text.')
        ),
    }


def _options_heading() -> SectionHeading:
    """The `Options` section, on line 5, before which the missing `Usage` section belongs."""
    return SectionHeading(level=2, text='Options', line=_line(5), empty=False, words=WordCount(UnsignedInt(3)))


def _document(corpus: str, filename: str) -> DocumentRef:
    return DocumentRef(CorpusName.parse(corpus), AspectFilename.parse(filename))


def _line(number: int) -> LineNumber:
    return LineNumber(NonZeroUnsignedInt(number))


def _latin_failure() -> Utf8Failure:
    return Utf8Failure(
        line=Line(NonZeroUnsignedInt(4)),
        offset=ByteOffset(UnsignedInt(31)),
        invalid=b'\xe9',
        reason=Utf8Reason.INVALID_CONTINUATION_BYTE,
    )


def _every_kind_of_report() -> tuple[RunReport, ...]:
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
        section=SectionName.parse('Usage'),
        before=_options_heading(),
        description='How to invoke the command.',
        example='Run `lorecraft check` from the repository root:\n\n```console\n$ lorecraft check\n```',
    )
    review = RootRelativePath.parse('.agents/skills/review')
    outside = EscapingSymlink(leaves_at=RootExit(ResolvedPath(review), _target('/home/alex/review')))
    a = _document('code', 'a')
    duplicate_name = DuplicateKey(owner=_CODE_OWNER, line=_line(3), key='name', first_line=_line(2), kept_line=_line(3))
    over_budget = TooManyTokens(spec=_CODE_SPEC, line=_line(1), overrun=overrun(2400, 2000))
    return (
        CheckedItem(
            ItemRef(check.path),
            diagnostics=(RuleDiagnostic(check.path, missing_usage, DefaultLevel(default_level(missing_usage))),),
            ungoverned=(SpecPart.FRONTMATTER, SpecPart.BUDGET),
        ),
        CheckedLayoutEntry(
            OutsideSymlinkRef(review),
            diagnostics=(RuleDiagnostic(review, outside, DefaultLevel(default_level(outside))),),
        ),
        UndecodableSubject(ItemRef(_document('code', 'latin').path), _latin_failure()),
        CheckedItem(
            ItemRef(a.path),
            diagnostics=(
                RuleDiagnostic(a.path, duplicate_name, DefaultLevel(default_level(duplicate_name))),
                RuleDiagnostic(a.path, over_budget, OverriddenLevel(Level.WARN, 'config', over_budget.CODE)),
            ),
            ungoverned=(),
        ),
        CheckedItem(
            ItemRef(_document('arch', 'adr').path),
            diagnostics=(),
            ungoverned=(SpecPart.STRUCTURE,),
        ),
    )


@pytest.mark.unit
class TestRenderText:
    def test_render_text_preserves_the_alias_used_by_a_level_flag(self) -> None:
        #: Given
        guide = _document('feat', 'guide')
        finding = MissingSection(
            spec=_FEAT_SPEC,
            section=SectionName.parse('Usage'),
            before=DocumentEnd(last_line=_line(9), after=None),
            description=None,
            example=None,
        )
        reports: tuple[RunReport, ...] = (
            CheckedItem(
                ItemRef(guide.path),
                diagnostics=(
                    RuleDiagnostic(
                        guide.path,
                        finding,
                        OverriddenLevel(Level.DENY, 'cli', WrittenSelector('MD040')),
                    ),
                ),
            ),
        )

        #: When
        text = render_text(reports, {}, _PLAIN)

        #: Then
        assert '  = note: -D MD040 requested on the command line' in text, (
            'the provenance note preserves the exact alias token passed to the flag'
        )

    def test_render_text_names_warning_elevation(self) -> None:
        #: Given
        guide = _document('feat', 'guide')
        finding = MissingSection(
            spec=_FEAT_SPEC,
            section=SectionName.parse('Usage'),
            before=DocumentEnd(last_line=_line(9), after=None),
            description=None,
            example=None,
        )
        reports: tuple[RunReport, ...] = (
            CheckedItem(
                ItemRef(guide.path),
                diagnostics=(RuleDiagnostic(guide.path, finding, ElevatedWarning()),),
            ),
        )

        #: When
        text = render_text(reports, {}, _PLAIN)

        #: Then
        assert '  = note: -D warnings elevated warning to error' in text, (
            'text diagnostics explain the post-resolution warning elevation'
        )

    def test_render_text_shows_note_for_non_default_level_source(self) -> None:
        #: Given
        guide = _document('feat', 'guide')
        finding = MissingSection(
            spec=_FEAT_SPEC,
            section=SectionName.parse('Usage'),
            before=DocumentEnd(last_line=_line(9), after=None),
            description=None,
            example=None,
        )
        reports: tuple[RunReport, ...] = (
            CheckedItem(
                ItemRef(guide.path),
                diagnostics=(RuleDiagnostic(guide.path, finding, OverriddenLevel(Level.DENY, 'cli', finding.CODE)),),
            ),
        )

        #: When
        text = render_text(reports, {}, _PLAIN)

        #: Then
        assert '  = note: -D LC306 requested on the command line' in text, (
            'text diagnostics identify a command-line deny override'
        )

    def test_render_text_with_a_warn_override_uses_its_flag_and_code_selector(self) -> None:
        #: Given
        guide = _document('feat', 'guide')
        finding = MissingSection(
            spec=_FEAT_SPEC,
            section=SectionName.parse('Usage'),
            before=DocumentEnd(last_line=_line(9), after=None),
            description=None,
            example=None,
        )
        reports: tuple[RunReport, ...] = (
            CheckedItem(
                ItemRef(guide.path),
                diagnostics=(
                    RuleDiagnostic(
                        guide.path,
                        finding,
                        OverriddenLevel(Level.WARN, 'cli', EscapingSymlink.CODE),
                    ),
                ),
            ),
        )

        #: When
        text = render_text(reports, {}, _PLAIN)

        #: Then
        assert '  = note: -W LC102 requested on the command line' in text, (
            'text diagnostics use the warn flag and the winning code selector'
        )

    def test_render_text_with_every_kind_of_report_matches_the_snapshot(self, snapshot: SnapshotAssertion) -> None:
        #: Given
        reports = _every_kind_of_report()
        expected = snapshot.use_extension(TextSnapshotExtension)
        sources = _sources()

        #: When
        text = render_text(reports, sources, _PLAIN)

        #: Then
        assert text == expected, 'the diagnostics of every kind of report match the reviewed snapshot'

    def test_render_text_with_no_report_prints_nothing(self) -> None:
        #: Given
        reports: tuple[RunReport, ...] = ()

        #: When
        text = render_text(reports, {}, _PLAIN)

        #: Then
        assert text == '', 'an empty run has no diagnostic to print'

    def test_render_text_without_unicode_draws_the_gutter_and_underlines_in_ascii(self) -> None:
        #: Given
        reports = _every_kind_of_report()
        style = TextStyle(color=False, unicode=False, width=80)
        sources = _sources()

        #: When
        text = render_text(reports, sources, style)

        #: Then
        assert ('2 | name: a\n  | ------- first written here\n3 | name: b\n  | ^^^^^^^ written again here') in text, (
            'the secondary label is underlined with dashes and the primary one with carets'
        )
        assert '│' not in text, 'no vertical box-drawing character is left'
        assert '─' not in text, 'no horizontal box-drawing character is left'
        assert '┄' not in text, 'no dashed box-drawing character is left'

    def test_render_text_with_colour_emphasises_the_severity_and_the_location(self) -> None:
        #: Given
        reports = _every_kind_of_report()
        style = TextStyle(color=True, unicode=True, width=80)
        sources = _sources()

        #: When
        text = render_text(reports, sources, style)

        #: Then
        assert '\x1b[31m\x1b[1merror[LC205]\x1b[0m' in text, 'an error is bold red'
        assert '\x1b[33m\x1b[1mwarning[LC401]\x1b[0m' in text, 'a warning is bold yellow'
        assert '\x1b[34m\x1b[1m-->\x1b[0m' in text, 'the location arrow is bold blue'

    def test_render_text_with_a_source_opening_with_a_byte_order_mark_underlines_the_visible_text(self) -> None:
        #: Given
        reports = _every_kind_of_report()
        sources = {
            RootRelativePath.parse('docs/code/a.md'): SourceText(
                ('\ufeff---', 'name: a', 'name: b', 'description: x', '---')
            ),
        }

        #: When
        text = render_text(reports, sources, _PLAIN)

        #: Then
        assert '\ufeff' not in text, 'the mark is not printed'
        assert '1 │ ---\n  │ ─── tokens over the budget: 400' in text, (
            'the line is printed without the mark and the underline spans the three visible characters'
        )

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
        sources = _sources()

        #: When
        text = render_text(reports, sources, style)

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
            section=SectionName.parse('Usage'),
            before=DocumentEnd(last_line=_line(9), after=None),
            description=None,
            example=f'{sample_line}\n  - and a nested one',
        )
        reports: tuple[RunReport, ...] = (
            CheckedItem(
                ItemRef(guide.path),
                diagnostics=(RuleDiagnostic(guide.path, missing_usage, DefaultLevel(default_level(missing_usage))),),
                ungoverned=(),
            ),
        )
        style = TextStyle(color=False, unicode=True, width=60)

        #: When
        text = render_text(reports, {}, style)

        #: Then
        assert f'          {sample_line}\n' in text, 'a line of a sample is drawn whole, however wide the terminal'
        assert '            - and a nested one' in text, 'the hanging indent of the sample survives'

    def test_render_text_with_a_form_feed_in_a_note_keeps_it_inside_its_line(self) -> None:
        #: Given
        guide = _document('feat', 'guide')
        missing_usage = MissingSection(
            spec=_FEAT_SPEC,
            section=SectionName.parse('Usage'),
            before=DocumentEnd(last_line=_line(9), after=None),
            description=None,
            example='one\x0ctwo\nthree',
        )
        reports: tuple[RunReport, ...] = (
            CheckedItem(
                ItemRef(guide.path),
                diagnostics=(RuleDiagnostic(guide.path, missing_usage, DefaultLevel(default_level(missing_usage))),),
                ungoverned=(),
            ),
        )

        #: When
        text = render_text(reports, {}, _PLAIN)

        #: Then
        assert '          one\x0ctwo\n          three' in text, 'a form feed ends no line, so the note has two lines'

    def test_render_text_with_a_lone_carriage_return_in_a_note_draws_each_side_as_a_line(self) -> None:
        #: Given
        guide = _document('feat', 'guide')
        missing_usage = MissingSection(
            spec=_FEAT_SPEC,
            section=SectionName.parse('Usage'),
            before=DocumentEnd(last_line=_line(9), after=None),
            description=None,
            example='one\rtwo',
        )
        reports: tuple[RunReport, ...] = (
            CheckedItem(
                ItemRef(guide.path),
                diagnostics=(RuleDiagnostic(guide.path, missing_usage, DefaultLevel(default_level(missing_usage))),),
                ungoverned=(),
            ),
        )

        #: When
        text = render_text(reports, {}, _PLAIN)

        #: Then
        assert '          one\n          two' in text, 'a lone `\\r` ends a line, as CommonMark has it'

    def test_render_text_with_a_note_of_padded_and_blank_lines_aligns_and_strips_them(self) -> None:
        #: Given
        guide = _document('feat', 'guide')
        # the example's first line ends in spaces, its second holds only spaces, and its third is indented
        missing_usage = MissingSection(
            spec=_FEAT_SPEC,
            section=SectionName.parse('Usage'),
            before=DocumentEnd(last_line=_line(9), after=None),
            description=None,
            example='Run it:  \n   \n    lorecraft check\n',
        )
        reports: tuple[RunReport, ...] = (
            CheckedItem(
                ItemRef(guide.path),
                diagnostics=(RuleDiagnostic(guide.path, missing_usage, DefaultLevel(default_level(missing_usage))),),
                ungoverned=(),
            ),
        )

        #: When
        text = render_text(reports, {}, _PLAIN)

        #: Then
        assert text == (
            'error[LC306]: missing required section `Usage`\n'
            ' --> docs/feat/guide.md:9\n'
            '  = at docs/feat/guide.md:9: expected `Usage` before the end of the document\n'
            ' ::: docs/__meta__/feat.spec.json\n'
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
            section=SectionName.parse('Usage'),
            before=DocumentEnd(last_line=_line(9), after=None),
            description=None,
            example='Run it:\r\n    lorecraft check',
        )
        reports: tuple[RunReport, ...] = (
            CheckedItem(
                ItemRef(guide.path),
                diagnostics=(RuleDiagnostic(guide.path, missing_usage, DefaultLevel(default_level(missing_usage))),),
                ungoverned=(),
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
            '.agents/skills/review: error[LC102]: symlink leads outside the repository\n'
            'docs/code/a.md:1: warning[LC401]: too many tokens (2400 > 2000)\n'
            "docs/code/a.md:3: error[LC205]: duplicate key 'name'\n"
            'docs/code/latin.md:4: error[LC001]: file is not valid UTF-8\n'
            'docs/feat/check.md:5: error[LC306]: missing required section `Usage`'
        ), 'a line holds the place, the severity, the code and the message, and the layout entry has no line'

    def test_render_short_with_no_report_prints_nothing(self) -> None:
        #: Given
        reports: tuple[RunReport, ...] = ()

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
        reports: tuple[RunReport, ...] = (
            CheckedItem(ItemRef(a.path), diagnostics=(), ungoverned=()),
            UndecodableSubject(ItemRef(_document('code', 'latin').path), _latin_failure()),
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
        reports: tuple[RunReport, ...] = ()

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
        assert text == ('LC0xx  1 error\nLC1xx  1 error\nLC2xx  1 error\nLC3xx  1 error\nLC4xx  1 warning'), (
            'each prefix is listed in order with its errors and warnings, each singular for one'
        )

    def test_render_prefix_summary_with_no_report_prints_nothing(self) -> None:
        #: Given
        reports: tuple[RunReport, ...] = ()

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
        document = json.loads(text)
        assert text == json.dumps(document, separators=(',', ':'), ensure_ascii=False), (
            'the document holds no indentation, no line break and no blank after a separator'
        )

    def test_render_json_with_each_coverage_case_keeps_the_published_keys_and_order(self) -> None:
        #: Given
        refused_path = RootRelativePath.parse('docs/code/b.md')
        dependency = RootRelativePath.parse('docs/__meta__/code.spec.json')
        reports: tuple[RunReport, ...] = (
            UncheckedSymlink(RootRelativePath.parse('docs/code/d.md')),
            RefusedSubject(ItemRef(refused_path), refused_path),
            BlockedSubject(ItemRef(RootRelativePath.parse('docs/code/c.md')), (dependency,)),
            CheckedItem(
                ItemRef(RootRelativePath.parse('docs/code/a.md')),
                diagnostics=(),
                ungoverned=(SpecPart.STRUCTURE,),
            ),
        )

        #: When
        text = render_json(reports)

        #: Then
        assert text == (
            '{"diagnostics":[],"summary":{"subjects":3,"errors":0,"warnings":0},"coverage":['
            '{"path":"docs/code/a.md","ungoverned":["structure"],"cause":null,"skipped_by":[]},'
            '{"path":"docs/code/b.md","ungoverned":[],"cause":"refused-path","skipped_by":["docs/code/b.md"]},'
            '{"path":"docs/code/c.md","ungoverned":[],"cause":"refused-dependency",'
            '"skipped_by":["docs/__meta__/code.spec.json"]},'
            '{"path":"docs/code/d.md","ungoverned":[],"cause":null,"skipped_by":[],"unchecked":true}]}'
        ), 'each typed coverage case retains its byte-for-byte JSON keys and field order'

    def test_render_json_with_a_non_ascii_key_writes_it_as_utf8(self) -> None:
        #: Given
        a = _document('code', 'a')
        duplicate_key = DuplicateKey(
            owner=_CODE_OWNER, line=_line(3), key='nom é', first_line=_line(2), kept_line=_line(3)
        )
        reports: tuple[RunReport, ...] = (
            CheckedItem(
                ItemRef(a.path),
                diagnostics=(RuleDiagnostic(a.path, duplicate_key, DefaultLevel(default_level(duplicate_key))),),
                ungoverned=(),
            ),
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
                    'level_source': 'default',
                    'code': 'LC102',
                    'name': 'escaping-symlink',
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
                    'level_source': 'config',
                    'code': 'LC401',
                    'name': 'too-many-tokens',
                    'message': 'too many tokens (2400 > 2000)',
                    'labels': [{'path': 'docs/code/a.md', 'line': 1, 'text': 'tokens over the budget: 400'}],
                    'children': [
                        {
                            'kind': 'note',
                            'text': 'the limit is set here',
                            'path': 'docs/__meta__/code.spec.json',
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
                    'level_source': 'default',
                    'code': 'LC205',
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
                            'path': 'docs/__meta__/code.spec.json',
                            'line': None,
                        },
                        {'kind': 'help', 'text': "write 'name' once, with the value meant", 'path': None, 'line': None},
                    ],
                },
                {
                    'path': 'docs/code/latin.md',
                    'line': 4,
                    'severity': 'error',
                    'level_source': 'default',
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
                    'level_source': 'default',
                    'code': 'LC306',
                    'name': 'missing-section',
                    'message': 'missing required section `Usage`',
                    'labels': [{'path': 'docs/feat/check.md', 'line': 5, 'text': 'expected `Usage` before `Options`'}],
                    'children': [
                        {
                            'kind': 'note',
                            'text': 'the document structure is set here',
                            'path': 'docs/__meta__/feat.spec.json',
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
                {'path': 'docs/arch/adr.md', 'ungoverned': ['structure'], 'cause': None, 'skipped_by': []},
                {
                    'path': 'docs/feat/check.md',
                    'ungoverned': ['frontmatter', 'budget'],
                    'cause': None,
                    'skipped_by': [],
                },
            ],
        }

        #: When
        text = render_json(reports)

        #: Then
        document = json.loads(text)
        assert document == expected, (
            'the document holds every diagnostic in output order, the summary, and the coverage in path order'
        )

    def test_render_json_with_no_report_encodes_every_key_empty(self) -> None:
        #: Given
        reports: tuple[RunReport, ...] = ()

        #: When
        text = render_json(reports)

        #: Then
        document = json.loads(text)
        assert document == {
            'diagnostics': [],
            'summary': {'subjects': 0, 'errors': 0, 'warnings': 0},
            'coverage': [],
        }, 'an empty run still writes every key'


def _reports_of_a_failed_spec() -> tuple[RunReport, ...]:
    """A run where the structure file of corpus `code` is malformed, handed over out of path order.

    - `docs/code/b.md` and `docs/code/a.md` have their structure-gated rules suppressed, since the corpus's structure
      file failed to load.
    - `docs/feat/check.md` is checked, ungoverned for its budget, and holds no diagnostic.
    - The structure file's failure is reported once, at the file, as a report of its own.
    """
    malformed = MalformedStructureFile(cause=FormatViolated(problems=('max_tokens: Extra inputs are not permitted',)))
    return (
        CheckedItem(
            ItemRef(_document('code', 'b').path),
            diagnostics=(),
            ungoverned=(SpecPart.STRUCTURE, SpecPart.OUTLINE),
        ),
        LoadFailureReport(_CODE_SPEC, malformed),
        CheckedItem(
            ItemRef(_document('feat', 'check').path),
            diagnostics=(),
            ungoverned=(SpecPart.BUDGET,),
        ),
        CheckedItem(
            ItemRef(_document('code', 'a').path),
            diagnostics=(),
            ungoverned=(SpecPart.STRUCTURE, SpecPart.OUTLINE),
        ),
    )


@pytest.mark.unit
class TestRenderLoadFailures:
    def test_render_coverage_with_failed_layer_lists_suppressed_parts_in_path_order(self) -> None:
        #: Given
        reports = _reports_of_a_failed_spec()

        #: When
        text = render_coverage(reports)

        #: Then
        assert text == (
            'docs/code/a.md: ungoverned for structure, outline\n'
            'docs/code/b.md: ungoverned for structure, outline\n'
            'docs/feat/check.md: ungoverned for budget'
        ), 'suppressed parts are coverage lines beside ungoverned parts'

    def test_render_coverage_with_a_refused_docs_path_names_the_refusal(self) -> None:
        #: Given
        report = BlockedSubject(
            ItemRef(_document('skills', 'review').path),
            (RootRelativePath.parse('docs/__meta__/code.spec.json'),),
        )

        #: When
        text = render_coverage((report,))

        #: Then
        assert text == (
            'docs/skills/review.md: skipped, depends on a refused docs path: docs/__meta__/code.spec.json'
        ), 'a refused docs target keeps its distinct coverage explanation'

    def test_render_summary_with_a_load_failure_counts_its_error_and_no_subject_for_it(self) -> None:
        #: Given
        reports = _reports_of_a_failed_spec()

        #: When
        text = render_summary(reports)

        #: Then
        assert text == 'checked 3 subject(s): 1 error(s), 0 warning(s)', (
            'all three decoded documents are subjects; the failure is an error, not a subject'
        )

    def test_render_short_with_a_load_failure_prints_one_line_at_its_path(self) -> None:
        #: Given
        reports = _reports_of_a_failed_spec()

        #: When
        text = render_short(reports)

        #: Then
        assert text == (
            'docs/__meta__/code.spec.json: error[LC003]: structure file does not follow the structure format'
        ), 'the failure is one line at the structure file'

    def test_render_prefix_summary_with_a_load_failure_counts_it_under_the_engine_group(self) -> None:
        #: Given
        reports = _reports_of_a_failed_spec()

        #: When
        text = render_prefix_summary(reports)

        #: Then
        assert text == 'LC0xx  1 error', 'a load failure is an engine diagnostic, so it is counted under its code range'

    def test_render_text_with_a_load_failure_draws_it_at_the_structure_file_with_its_notes(self) -> None:
        #: Given
        reports = _reports_of_a_failed_spec()

        #: When
        text = render_text(reports, {}, _PLAIN)

        #: Then
        assert text == (
            'error[LC003]: structure file does not follow the structure format\n'
            ' --> docs/__meta__/code.spec.json\n'
            '  = help: fix each problem listed\n'
            '  = note: max_tokens: Extra inputs are not permitted'
        ), 'the failure is drawn like any diagnostic of a whole file, with each problem as a note after the help'

    def test_render_json_with_failed_layers_lists_suppressed_parts_in_coverage(self) -> None:
        #: Given
        reports = _reports_of_a_failed_spec()

        #: When
        text = render_json(reports)

        #: Then
        document = json.loads(text)
        assert document['summary'] == {'subjects': 3, 'errors': 1, 'warnings': 0}, 'the failure is no subject'
        assert document['coverage'] == [
            {'path': 'docs/code/a.md', 'ungoverned': ['structure', 'outline'], 'cause': None, 'skipped_by': []},
            {'path': 'docs/code/b.md', 'ungoverned': ['structure', 'outline'], 'cause': None, 'skipped_by': []},
            {'path': 'docs/feat/check.md', 'ungoverned': ['budget'], 'cause': None, 'skipped_by': []},
        ], 'failed-layer-suppressed parts and ungoverned parts share the coverage field'
        assert document['diagnostics'] == [
            {
                'path': 'docs/__meta__/code.spec.json',
                'line': None,
                'severity': 'error',
                'level_source': 'default',
                'code': 'LC003',
                'name': 'malformed-structure-file',
                'message': 'structure file does not follow the structure format',
                'labels': [],
                'children': [
                    {'kind': 'help', 'text': 'fix each problem listed', 'path': None, 'line': None},
                    {'kind': 'note', 'text': 'max_tokens: Extra inputs are not permitted', 'path': None, 'line': None},
                ],
            }
        ], 'the failure is the one diagnostic, at the structure file, with its code, and no level lowers it'
