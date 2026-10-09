"""Render what a run of the rules engine reports as short lines and JSON, and count it: the coverage and the summaries.

Pure: the subject reports arrive as values, and each function returns the text a command prints, so nothing here
reads the disk or writes to a stream. The diagnostics as text for a person are drawn by `diagnostic_text`. As short
lines, one per diagnostic, they are what a command prints on stdout for a tool to match; the coverage lines and the
summaries are what it prints on stderr; as JSON, one compact document carries the diagnostics, the summary and the
coverage.

Every diagnostic of every report is printed in the order `diagnostic_order` states, whatever order the reports
arrive in, so one revision always prints the same output. A short line reads, with the line left out for a subject
with no lines, such as a layout entry or a file that did not decode:

    docs/code/a.md:3: error[FM005]: duplicate key 'name'
"""

from typing import Literal, assert_never

from pydantic import BaseModel, ConfigDict

from lorecraft.checks import CheckedLayoutEntry, CheckedSubject, Diagnostic, SubjectReport, UndecodableSubject
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import Severity

from .diagnostic_parts import child_kind, child_place, format_place, ordered_diagnostics, place, primary_line

# The JSON `render_json` prints, one `BaseModel` per object, so a misspelt or missing key fails the type check. The
# keys are the command's published output: renaming one is a change to that contract, not a refactor. A field is
# printed in the order it is declared, and `None` is printed as `null`.


class _LabelJson(BaseModel):
    """One label of a diagnostic.

    Attributes:
        path: The file the label points at: the subject's own path for a line of the subject.
        line: The line it points at, or None when it points at the whole of another file.
        text: What the label says about that place.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    line: int | None
    text: str


class _ChildJson(BaseModel):
    """One help or note of a diagnostic.

    Attributes:
        kind: `help` for how to fix the diagnostic, `note` for context that explains it.
        text: What it says; it may span several lines.
        path: The file it points at, or None when it points nowhere.
        line: The line it points at, or None when it points nowhere or at a whole file.
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal['help', 'note']
    text: str
    path: str | None
    line: int | None


class _DiagnosticJson(BaseModel):
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

    model_config = ConfigDict(frozen=True)

    path: str
    line: int | None
    severity: Literal['error', 'warning']
    code: str
    name: str
    message: str
    labels: list[_LabelJson]
    children: list[_ChildJson]


class _SummaryJson(BaseModel):
    """What the run counted.

    Attributes:
        subjects: The subjects reported, whatever they held.
        errors: The diagnostics reported as errors.
        warnings: The diagnostics reported as warnings.
    """

    model_config = ConfigDict(frozen=True)

    subjects: int
    errors: int
    warnings: int


class _CoverageJson(BaseModel):
    """One subject an enabled rule could not judge, for want of a specification governing it.

    Attributes:
        path: The subject.
        ungoverned: The facets no specification governs it for, in the order its report holds them.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    ungoverned: list[str]


class _ReportJson(BaseModel):
    """The whole document.

    Attributes:
        diagnostics: Every diagnostic of the run, in output order.
        summary: What the run counted.
        coverage: Every subject with an ungoverned facet, in path order; none when every subject is governed.
    """

    model_config = ConfigDict(frozen=True)

    diagnostics: list[_DiagnosticJson]
    summary: _SummaryJson
    coverage: list[_CoverageJson]


def render_short(reports: tuple[SubjectReport, ...]) -> str:
    """Every diagnostic of the run as one line, in the order `diagnostic_order` sorts them into.

    A line reads `{path}:{line}: {severity}[{code}]: {message}`, and `{path}: ...` for a diagnostic of the whole
    subject. Labels, help and notes are left out.

    Args:
        reports: One report per subject the run checked, in any order.

    Returns:
        The lines, newline-separated, without a trailing newline; empty when the run found nothing.
    """
    lines: list[str] = []
    for diagnostic in ordered_diagnostics(reports):
        occurrence = diagnostic.occurrence
        line = primary_line(diagnostic)
        head = f'{diagnostic.severity.value}[{occurrence.CODE}]: {occurrence.message()}'
        lines.append(f'{format_place(diagnostic.path, line)}: {head}')
    return '\n'.join(lines)


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
    errors, warnings = _count_severities(ordered_diagnostics(reports))
    return f'checked {len(reports)} subject(s): {errors} error(s), {warnings} warning(s)'


def render_prefix_summary(reports: tuple[SubjectReport, ...]) -> str:
    """One line per code prefix that reported, with its errors and warnings, in prefix order.

    A line reads `{prefix}  {errors}, {warnings}`, each count left out when it is zero, such as `OUT  2 errors, 1
    warning`.

    Args:
        reports: One report per subject the run checked, in any order.

    Returns:
        The lines, newline-separated, without a trailing newline; empty when the run found nothing.
    """
    by_prefix: dict[str, list[Diagnostic]] = {}
    for diagnostic in ordered_diagnostics(reports):
        by_prefix.setdefault(str(diagnostic.occurrence.CODE.group.prefix), []).append(diagnostic)

    prefix_width = max((len(prefix) for prefix in by_prefix), default=0)
    lines: list[str] = []
    for prefix in sorted(by_prefix):
        errors, warnings = _count_severities(by_prefix[prefix])
        counts: list[str] = []
        if errors:
            counts.append(_count(errors, 'error'))
        if warnings:
            counts.append(_count(warnings, 'warning'))
        lines.append(f'{prefix:<{prefix_width}}  {", ".join(counts)}')
    return '\n'.join(lines)


def render_json(reports: tuple[SubjectReport, ...]) -> str:
    """The run as one compact JSON document: its diagnostics, its summary and its coverage, every key always present.

    The diagnostics are in the order `diagnostic_order` states, as `render_text` and `render_short` print them, and
    the coverage in the order `render_coverage` prints it.

    Args:
        reports: One report per subject the run checked, in any order.
    """
    diagnostics = ordered_diagnostics(reports)
    diagnostic_objects: list[_DiagnosticJson] = []
    for diagnostic in diagnostics:
        diagnostic_objects.append(_json_diagnostic(diagnostic))
    errors, warnings = _count_severities(diagnostics)
    coverage: list[_CoverageJson] = []
    for subject in _ungoverned_subjects(reports):
        facets: list[str] = []
        for facet in subject.ungoverned:
            facets.append(facet.value)
        coverage.append(_CoverageJson(path=str(subject.ref.path), ungoverned=facets))
    document = _ReportJson(
        diagnostics=diagnostic_objects,
        summary=_SummaryJson(subjects=len(reports), errors=errors, warnings=warnings),
        coverage=coverage,
    )
    return document.model_dump_json()


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


def _json_diagnostic(diagnostic: Diagnostic) -> _DiagnosticJson:
    """One diagnostic as a JSON object, its labels and its help and notes in the order the occurrence gives them.

    Args:
        diagnostic: The diagnostic to encode.
    """
    occurrence = diagnostic.occurrence
    labels: list[_LabelJson] = []
    for label in occurrence.labels():
        path, line = place(diagnostic.path, label.at)
        labels.append(_LabelJson(path=str(path), line=_json_line(line), text=label.text))
    children: list[_ChildJson] = []
    for child in occurrence.children():
        child_path, child_line = child_place(diagnostic.path, child)
        children.append(
            _ChildJson(
                kind=child_kind(child),
                text=child.text,
                path=None if child_path is None else str(child_path),
                line=_json_line(child_line),
            )
        )
    return _DiagnosticJson(
        path=str(diagnostic.path),
        line=_json_line(primary_line(diagnostic)),
        severity=_severity_word(diagnostic.severity),
        code=str(occurrence.CODE),
        name=str(occurrence.NAME),
        message=occurrence.message(),
        labels=labels,
        children=children,
    )


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


def _json_line(line: LineNumber | None) -> int | None:
    """A line as JSON writes it: its number, or null when there is none.

    Args:
        line: The line a diagnostic, label, help or note points at, or None when it points at no line.
    """
    if line is None:
        return None
    return line.number


def _count(number: int, noun: str) -> str:
    """A count with its noun, pluralised with an `s` unless it is one.

    Args:
        number: How many there are.
        noun: What there are, in the singular.
    """
    if number == 1:
        return f'{number} {noun}'
    return f'{number} {noun}s'
