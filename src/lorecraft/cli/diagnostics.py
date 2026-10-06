"""Render what a run of the rules engine reports: the diagnostics, the coverage, the summary, and the JSON document.

Pure: the subject reports arrive as values, and each function returns the text a command prints, so nothing here
reads the disk or writes to a stream. As text, the diagnostics are what a command prints on stdout, and the coverage
lines and the summary line what it prints on stderr; as JSON, one document carries all three.

Every diagnostic of every report is printed in the order `diagnostic_order` states, whatever order the reports
arrive in, so one revision always prints the same output. A diagnostic prints as its primary line, then one line per
label, then its help and notes, and an empty line separates it from the next:

    docs/code/a.md:3: error[FM005]: duplicate key 'name', already written on line 2
      --> docs/code/a.md:2: first written here
      = note: the frontmatter schema is set here (docs/__meta__/code.structure.json)
      = help: write 'name' once, with the value meant

A subject with no lines, such as a layout entry or a file that did not decode, prints its path without a line.
"""

import json
from typing import Literal, TypedDict, assert_never

from lorecraft.checks.report import (
    CheckedLayoutEntry,
    CheckedSubject,
    Diagnostic,
    SubjectReport,
    UndecodableSubject,
    diagnostic_order,
)
from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import (
    Elsewhere,
    EntryHelp,
    EntryNote,
    EntrySubdiagnostic,
    Help,
    Here,
    Note,
    Subdiagnostic,
    WholeSubject,
)

# The JSON `render_json` prints, one `TypedDict` per object, so a misspelt or missing key fails the type check. The
# keys are the command's published output: renaming one is a change to that contract, not a refactor.


class _LabelJson(TypedDict):
    """One label of a diagnostic.

    Attributes:
        path: The file the label points at: the subject's own path for a line of the subject.
        line: The line it points at, or None when it points at the whole of another file.
        text: What the label says about that place.
    """

    path: str
    line: int | None
    text: str


class _ChildJson(TypedDict):
    """One help or note of a diagnostic.

    Attributes:
        kind: `help` for how to fix the diagnostic, `note` for context that explains it.
        text: What it says; it may span several lines.
        path: The file it points at, or None when it points nowhere.
        line: The line it points at, or None when it points nowhere or at a whole file.
    """

    kind: Literal['help', 'note']
    text: str
    path: str | None
    line: int | None


class _DiagnosticJson(TypedDict):
    """One diagnostic.

    Attributes:
        path: The subject the diagnostic was found in.
        line: The line it is reported at, or None when it concerns the whole subject.
        severity: `error` or `warning`.
        code: The code of the rule or engine condition, such as `FM005`.
        name: The kebab-case name of the rule or engine condition, such as `duplicate-key`.
        message: What is wrong, on one line.
        labels: The labelled locations, in the order the occurrence gives them.
        children: The help and notes, in the order the occurrence gives them; the specification that states the
            rule travels as one of them, a note pointing at it.
    """

    path: str
    line: int | None
    severity: Literal['error', 'warning']
    code: str
    name: str
    message: str
    labels: list[_LabelJson]
    children: list[_ChildJson]


class _SummaryJson(TypedDict):
    """What the run counted.

    Attributes:
        subjects: The subjects reported, whatever they held.
        errors: The diagnostics reported as errors.
        warnings: The diagnostics reported as warnings.
    """

    subjects: int
    errors: int
    warnings: int


class _CoverageJson(TypedDict):
    """One subject an enabled rule could not judge, for want of a specification governing it.

    Attributes:
        path: The subject.
        ungoverned: The facets no specification governs it for, in the order its report holds them.
    """

    path: str
    ungoverned: list[str]


class _ReportJson(TypedDict):
    """The whole document.

    Attributes:
        diagnostics: Every diagnostic of the run, in output order.
        summary: What the run counted.
        coverage: Every subject with an ungoverned facet, in path order; none when every subject is governed.
    """

    diagnostics: list[_DiagnosticJson]
    summary: _SummaryJson
    coverage: list[_CoverageJson]


def render_diagnostics(reports: tuple[SubjectReport, ...]) -> str:
    """Every diagnostic of the run as text, in the order `diagnostic_order` sorts them into.

    Args:
        reports: One report per subject the run checked, in any order.

    Returns:
        The diagnostics, an empty line between two of them, as the established compilers separate theirs, so a
        note whose own text holds an empty line never runs into the next diagnostic; no trailing newline, and
        empty when the run found nothing.
    """
    blocks: list[str] = []
    for diagnostic in _ordered_diagnostics(reports):
        blocks.append('\n'.join(_diagnostic_lines(diagnostic)))
    return '\n\n'.join(blocks)


def render_coverage(reports: tuple[SubjectReport, ...]) -> str:
    """One line per checked subject with a facet no specification governs, in path order.

    A line reads `{path}: ungoverned for {facets}`, the facets comma-separated in the order the report holds them. A
    subject that did not decode and a layout entry are never ungoverned, so they never print one.

    Args:
        reports: One report per subject the run checked, in any order.

    Returns:
        The lines, newline-separated, without a trailing newline; empty when every subject is governed.
    """
    lines: list[str] = []
    for subject in _ungoverned_subjects(reports):
        facets = ', '.join(facet.value for facet in subject.ungoverned)
        lines.append(f'{subject.ref.path}: ungoverned for {facets}')
    return '\n'.join(lines)


def render_summary(reports: tuple[SubjectReport, ...]) -> str:
    """The one summary line: the subjects checked, then the errors and the warnings among their diagnostics.

    Args:
        reports: One report per subject the run checked; each counts as one subject, whatever it held.
    """
    errors, warnings = _count_severities(_ordered_diagnostics(reports))
    return f'checked {len(reports)} subject(s): {errors} error(s), {warnings} warning(s)'


def render_json(reports: tuple[SubjectReport, ...]) -> str:
    """The run as one JSON document: its diagnostics, its summary and its coverage, every key always present.

    The diagnostics are in the order `render_diagnostics` prints them, and the coverage in the order
    `render_coverage` prints it.

    Args:
        reports: One report per subject the run checked, in any order.
    """
    diagnostics = _ordered_diagnostics(reports)
    diagnostic_objects: list[_DiagnosticJson] = []
    for diagnostic in diagnostics:
        diagnostic_objects.append(_json_diagnostic(diagnostic))
    errors, warnings = _count_severities(diagnostics)
    coverage: list[_CoverageJson] = []
    for subject in _ungoverned_subjects(reports):
        facets: list[str] = []
        for facet in subject.ungoverned:
            facets.append(facet.value)
        coverage.append({'path': str(subject.ref.path), 'ungoverned': facets})
    document: _ReportJson = {
        'diagnostics': diagnostic_objects,
        'summary': {'subjects': len(reports), 'errors': errors, 'warnings': warnings},
        'coverage': coverage,
    }
    return json.dumps(document)


def _ordered_diagnostics(reports: tuple[SubjectReport, ...]) -> list[Diagnostic]:
    """Every diagnostic of every report, sorted into output order across the reports.

    Each report already holds its own in that order, but the reports may arrive in any order, so the whole run is
    sorted again.

    Args:
        reports: One report per subject the run checked, in any order.
    """
    diagnostics: list[Diagnostic] = []
    for report in reports:
        diagnostics.extend(report.diagnostics)
    return sorted(diagnostics, key=diagnostic_order)


def _ungoverned_subjects(reports: tuple[SubjectReport, ...]) -> list[CheckedSubject]:
    """The checked subjects with at least one ungoverned facet, by their path compared by code point.

    Args:
        reports: One report per subject the run checked, in any order.
    """
    subjects: list[CheckedSubject] = []
    for report in reports:
        match report:
            case CheckedSubject():
                if report.ungoverned:
                    subjects.append(report)
            case UndecodableSubject() | CheckedLayoutEntry():
                pass  # neither can be ungoverned: one was never judged, the other has no specification
            case _:
                assert_never(report)
    # A path compares as its string, the way `DiagnosticOrder.path` does, so both outputs share one path order.
    return sorted(subjects, key=lambda subject: str(subject.ref.path))


def _count_severities(diagnostics: list[Diagnostic]) -> tuple[int, int]:
    """How many of the diagnostics are errors, and how many warnings, in that order.

    Args:
        diagnostics: The diagnostics to count, each by the severity it is reported at.
    """
    errors = 0
    warnings = 0
    for diagnostic in diagnostics:
        match diagnostic.severity:
            case Severity.ERROR:
                errors += 1
            case Severity.WARNING:
                warnings += 1
            case _:
                assert_never(diagnostic.severity)
    return errors, warnings


def _diagnostic_lines(diagnostic: Diagnostic) -> list[str]:
    """The lines one diagnostic prints as: its primary line, a line per label, then its help and notes.

    Args:
        diagnostic: The diagnostic to print.
    """
    occurrence = diagnostic.occurrence
    head = f'{diagnostic.severity.value}[{occurrence.CODE}]: {occurrence.message()}'
    line = _primary_line(diagnostic)
    if line is None:
        lines = [f'{diagnostic.path}: {head}']
    else:
        lines = [f'{diagnostic.path}:{line}: {head}']
    for label in occurrence.labels():
        path, label_line = _place(diagnostic.path, label.at)
        lines.append(f'  --> {_format_place(path, label_line)}: {label.text}')
    for child in occurrence.children():
        lines.extend(_child_lines(diagnostic.path, child))
    return lines


def _child_lines(subject: RootRelativePath, child: Subdiagnostic | EntrySubdiagnostic) -> list[str]:
    """The lines one help or note prints as, its kind on the first and its text aligned under itself.

    The place it points at, if any, is appended to the first line in parentheses.

    Args:
        subject: The path of the subject the diagnostic was found in, which a line of the subject is reported at.
        child: The help or note to print; each line of its text becomes one output line, a trailing line break adds
            none, and a CRLF break counts as one.
    """
    prefix = f'  = {_child_kind(child)}: '
    indent = ' ' * len(prefix)
    # `splitlines` rather than `split('\n')`: it drops the empty piece after a trailing line break and the `\r` of a
    # CRLF one. A text with no lines at all still prints its prefix.
    first, *rest = child.text.splitlines() or ['']
    # Trailing whitespace is stripped from every line, which leaves a whitespace-only line empty; leading
    # indentation is kept, so a sample's nesting survives.
    first_line = f'{prefix}{first}'.rstrip()
    path, line = _child_place(subject, child)
    if path is not None:
        first_line = f'{first_line} ({_format_place(path, line)})'
    lines = [first_line]
    for text_line in rest:
        content = text_line.rstrip()
        if content:
            lines.append(f'{indent}{content}')
        else:
            lines.append('')
    return lines


def _json_diagnostic(diagnostic: Diagnostic) -> _DiagnosticJson:
    """One diagnostic as a JSON object, its labels and its help and notes in the order the occurrence gives them.

    Args:
        diagnostic: The diagnostic to encode.
    """
    occurrence = diagnostic.occurrence
    labels: list[_LabelJson] = []
    for label in occurrence.labels():
        path, line = _place(diagnostic.path, label.at)
        labels.append({'path': str(path), 'line': _json_line(line), 'text': label.text})
    children: list[_ChildJson] = []
    for child in occurrence.children():
        child_path, child_line = _child_place(diagnostic.path, child)
        children.append(
            {
                'kind': _child_kind(child),
                'text': child.text,
                'path': None if child_path is None else str(child_path),
                'line': _json_line(child_line),
            }
        )
    return {
        'path': str(diagnostic.path),
        'line': _json_line(_primary_line(diagnostic)),
        'severity': _severity_word(diagnostic.severity),
        'code': str(occurrence.CODE),
        'name': str(occurrence.NAME),
        'message': occurrence.message(),
        'labels': labels,
        'children': children,
    }


def _primary_line(diagnostic: Diagnostic) -> LineNumber | None:
    """The line a diagnostic is reported at, or None when it concerns the whole subject.

    Args:
        diagnostic: The diagnostic whose primary location is read.
    """
    primary = diagnostic.occurrence.primary()
    match primary:
        case Here():
            return primary.line
        case WholeSubject():
            return None
        case _:
            assert_never(primary)


def _child_place(
    subject: RootRelativePath, child: Subdiagnostic | EntrySubdiagnostic
) -> tuple[RootRelativePath | None, LineNumber | None]:
    """The file and the line a help or note points at; both None when it points nowhere.

    Args:
        subject: The path of the subject the diagnostic was found in, which a line of the subject is reported at.
        child: The help or note whose place is read.
    """
    if child.at is None:
        return None, None
    return _place(subject, child.at)


def _place(subject: RootRelativePath, at: Here | Elsewhere) -> tuple[RootRelativePath, LineNumber | None]:
    """The file and the line a location names; the line is None for the whole of another file.

    Args:
        subject: The path of the subject the diagnostic was found in, which `Here` names a line of.
        at: Where a label, help or note points: a line of the subject, or another file or a line in it.
    """
    match at:
        case Here():
            return subject, at.line
        case Elsewhere():
            return at.path, at.line
        case _:
            assert_never(at)


def _format_place(path: RootRelativePath, line: LineNumber | None) -> str:
    """A place as text: `path:line`, or the path alone for a whole file.

    Args:
        path: The file the place is in, printed as it is.
        line: The line the place points at in that file, or None when it points at the whole file.
    """
    if line is None:
        return str(path)
    return f'{path}:{line}'


def _severity_word(severity: Severity) -> Literal['error', 'warning']:
    """The word a severity is written as in the JSON document.

    Args:
        severity: The severity a diagnostic is reported at.
    """
    match severity:
        case Severity.ERROR:
            return 'error'
        case Severity.WARNING:
            return 'warning'
        case _:
            assert_never(severity)


def _child_kind(child: Subdiagnostic | EntrySubdiagnostic) -> Literal['help', 'note']:
    """The word a help or note is printed under.

    Args:
        child: The help or note whose kind names the word: `help` for a help, `note` for a note.
    """
    match child:
        case Help() | EntryHelp():
            return 'help'
        case Note() | EntryNote():
            return 'note'
        case _:
            assert_never(child)


def _json_line(line: LineNumber | None) -> int | None:
    """A line as JSON writes it: its number, or null when there is none.

    Args:
        line: The line a diagnostic, label, help or note points at, or None when it points at no line.
    """
    if line is None:
        return None
    return line.number
