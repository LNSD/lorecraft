"""Render what a run of the rules engine reports as short lines and JSON, and count it: the coverage and the summaries.

Pure: the subject reports arrive as values, and each function returns the text a command prints, so nothing here
reads the disk or writes to a stream. The diagnostics as text for a person are drawn by `diagnostic_text`. As short
lines, one per diagnostic, they are what a command prints on stdout for a tool to match; the coverage lines and the
summaries are what it prints on stderr; as JSON, one compact document carries the diagnostics, the summary and the
coverage. The coverage lists subjects with ungoverned or failed-layer-suppressed spec parts, and subjects skipped
because their own read or a docs dependency was refused.

Every diagnostic of every report is printed in the order `diagnostic_order` states, whatever order the reports
arrive in, so one revision always prints the same output. A short line reads, with the line left out for a subject
with no lines, such as a layout entry or a file that did not decode:

    docs/code/a.md:3: error[FM005]: duplicate key 'name'
"""

from dataclasses import dataclass
from typing import Literal, assert_never

from pydantic import BaseModel, ConfigDict

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.rules.identity import Severity
from lorecraft.rules.report import (
    BlockedSubject,
    CheckedItem,
    CheckedLayoutEntry,
    Diagnostic,
    LoadFailureReport,
    RefusedSubject,
    RunReport,
    UncheckedSymlink,
    UndecodableSubject,
)

from .diagnostic_parts import (
    FilePlace,
    child_kind,
    child_place,
    format_place,
    ordered_diagnostics,
    place,
    primary_line,
)

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
    line: NonZeroUnsignedInt | None
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
    line: NonZeroUnsignedInt | None


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
    line: NonZeroUnsignedInt | None
    severity: Literal['error', 'warning']
    code: str
    name: str
    message: str
    labels: list[_LabelJson]
    children: list[_ChildJson]


class _SummaryJson(BaseModel):
    """What the run counted.

    Attributes:
        subjects: The subjects reported, whatever they held; a load failure is no subject, so it is not counted.
        errors: The diagnostics reported as errors.
        warnings: The diagnostics reported as warnings.
    """

    model_config = ConfigDict(frozen=True)

    subjects: int
    errors: int
    warnings: int


class _CoverageJson(BaseModel):
    """One subject with ungoverned or failed-layer-suppressed spec parts, or skipped.

    Attributes:
        path: The subject.
        ungoverned: The spec parts no specification governs it for, or which a failed layer suppresses;
            in report order, and none for a skipped subject.
        cause: Why the subject was skipped, or None for a subject that was judged.
        skipped_by: Refused paths the subject depends on; empty for a subject that was judged.
    """

    model_config = ConfigDict(frozen=True)

    path: str
    ungoverned: list[str]
    cause: Literal['refused-path', 'refused-dependency'] | None
    skipped_by: list[str]
    unchecked: bool = False


class _ReportJson(BaseModel):
    """The whole document.

    Attributes:
        diagnostics: Every diagnostic of the run, in output order.
        summary: What the run counted.
        coverage: Every subject with an ungoverned spec part and every skipped subject, in path order;
            none when every subject was judged for every governed part.
    """

    model_config = ConfigDict(frozen=True)

    diagnostics: list[_DiagnosticJson]
    summary: _SummaryJson
    coverage: list[_CoverageJson]


def render_short(reports: tuple[RunReport, ...]) -> str:
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
        head = f'{diagnostic.severity}[{occurrence.CODE}]: {occurrence.message()}'
        lines.append(f'{format_place(FilePlace(diagnostic.path, line))}: {head}')
    return '\n'.join(lines)


def render_coverage(reports: tuple[RunReport, ...]) -> str:
    """One line per subject no rule judged for some spec part or at all, in path order.

    A checked item with an ungoverned or failed-layer-suppressed spec part reads
    `{path}: ungoverned for {facets}`, with the parts comma-separated in report order. A subject skipped because a
    refused read reads `{path}: skipped, read refused at: {files}`; a refused dependency reads
    `{path}: skipped, depends on a refused docs path: {files}`. Files are comma-separated in path or layer order,
    respectively. A subject that did not decode and a layout entry are never ungoverned or skipped, so they never
    print one.

    Args:
        reports: One report per subject the run checked, in any order.

    Returns:
        The lines, newline-separated, without a trailing newline; empty when every subject was judged in full.
    """
    lines: list[str] = []
    for subject in _coverage_subjects(reports):
        match subject:
            case CheckedItem():
                facets = ', '.join(subject.ungoverned)
                lines.append(f'{subject.ref.path}: ungoverned for {facets}')
            case RefusedSubject():
                lines.append(f'{subject.ref.path}: skipped, read refused at: {subject.path}')
            case BlockedSubject():
                files = ', '.join(str(path) for path in subject.refused_paths)
                lines.append(f'{subject.ref.path}: skipped, depends on a refused docs path: {files}')
            case UncheckedSymlink():
                lines.append(f'{subject.path}: not checked (symlink)')
            case _:
                assert_never(subject)
    return '\n'.join(lines)


def render_summary(reports: tuple[RunReport, ...]) -> str:
    """The one summary line: the subjects checked, then the errors and the warnings among their diagnostics.

    Args:
        reports: One report per subject the run checked, and one per load failure; each subject counts as one,
            whatever it held, and a load failure counts as none.
    """
    severities = _count_severities(ordered_diagnostics(reports))
    return (
        f'checked {_count_subjects(reports)} subject(s): {severities.errors} error(s), {severities.warnings} warning(s)'
    )


def render_prefix_summary(reports: tuple[RunReport, ...]) -> str:
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
        severities = _count_severities(by_prefix[prefix])
        counts: list[str] = []
        if severities.errors:
            counts.append(_count(severities.errors, 'error'))
        if severities.warnings:
            counts.append(_count(severities.warnings, 'warning'))
        lines.append(f'{prefix:<{prefix_width}}  {", ".join(counts)}')
    return '\n'.join(lines)


def render_json(reports: tuple[RunReport, ...]) -> str:
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
    severities = _count_severities(diagnostics)
    coverage: list[_CoverageJson] = []
    for subject in _coverage_subjects(reports):
        match subject:
            case CheckedItem():
                facets: list[str] = []
                for facet in subject.ungoverned:
                    facets.append(facet)
                coverage.append(_CoverageJson(path=str(subject.ref.path), ungoverned=facets, cause=None, skipped_by=[]))
            case RefusedSubject():
                coverage.append(
                    _CoverageJson(
                        path=str(subject.ref.path),
                        ungoverned=[],
                        cause='refused-path',
                        skipped_by=[str(subject.path)],
                    )
                )
            case BlockedSubject():
                refused_paths: list[str] = []
                for path in subject.refused_paths:
                    refused_paths.append(str(path))
                coverage.append(
                    _CoverageJson(
                        path=str(subject.ref.path),
                        ungoverned=[],
                        cause='refused-dependency',
                        skipped_by=refused_paths,
                    )
                )
            case UncheckedSymlink():
                coverage.append(
                    _CoverageJson(path=str(subject.path), ungoverned=[], cause=None, skipped_by=[], unchecked=True)
                )
            case _:
                assert_never(subject)
    document = _ReportJson(
        diagnostics=diagnostic_objects,
        summary=_SummaryJson(subjects=_count_subjects(reports), errors=severities.errors, warnings=severities.warnings),
        coverage=coverage,
    )
    return document.model_dump_json(exclude_defaults=True)


def _coverage_subjects(
    reports: tuple[RunReport, ...],
) -> list[CheckedItem | RefusedSubject | BlockedSubject | UncheckedSymlink]:
    """The checked documents with ungoverned spec parts and skipped ones, compared by path code point.

    Args:
        reports: One report per subject the run checked, in any order.
    """
    subjects: list[CheckedItem | RefusedSubject | BlockedSubject | UncheckedSymlink] = []
    for report in reports:
        match report:
            case CheckedItem():
                if report.ungoverned:
                    subjects.append(report)
            case RefusedSubject() | BlockedSubject():
                subjects.append(report)
            case UncheckedSymlink():
                subjects.append(report)
            case UndecodableSubject() | CheckedLayoutEntry() | LoadFailureReport():
                # None was judged in part: one never decoded, a layout entry has no
                # specification, and a load failure is no subject.
                pass
            case _:
                assert_never(report)
    # A path compares as its string, the way `DiagnosticOrder.path` does, so both outputs share one path order.
    return sorted(
        subjects, key=lambda subject: str(subject.path if isinstance(subject, UncheckedSymlink) else subject.ref.path)
    )


def _count_subjects(reports: tuple[RunReport, ...]) -> int:
    """How many reports are of a subject: every one but a load failure, which is filed at a unit, not a subject.

    Args:
        reports: One report per subject the run checked, and one per load failure.
    """
    count = 0
    for report in reports:
        match report:
            case CheckedItem() | UndecodableSubject() | CheckedLayoutEntry() | RefusedSubject() | BlockedSubject():
                count += 1
            case UncheckedSymlink():
                pass
            case LoadFailureReport():
                pass  # filed at a unit of the declaration, not at a subject
            case _:
                assert_never(report)
    return count


@dataclass(frozen=True, slots=True)
class _SeverityCounts:
    """How many diagnostics a run reported at each severity.

    Attributes:
        errors: The diagnostics reported as errors.
        warnings: The diagnostics reported as warnings.
    """

    errors: int
    warnings: int


def _count_severities(diagnostics: list[Diagnostic]) -> _SeverityCounts:
    """How many of the diagnostics are errors, and how many warnings.

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
    return _SeverityCounts(errors=errors, warnings=warnings)


def _json_diagnostic(diagnostic: Diagnostic) -> _DiagnosticJson:
    """One diagnostic as a JSON object, its labels and its help and notes in the order the occurrence gives them.

    Args:
        diagnostic: The diagnostic to encode.
    """
    occurrence = diagnostic.occurrence
    labels: list[_LabelJson] = []
    for label in occurrence.labels():
        at = place(diagnostic.path, label.at)
        labels.append(_LabelJson(path=str(at.path), line=at.line, text=label.text))
    children: list[_ChildJson] = []
    for child in occurrence.children():
        child_at = child_place(diagnostic.path, child)
        if child_at is None:
            children.append(_ChildJson(kind=child_kind(child), text=child.text, path=None, line=None))
        else:
            children.append(
                _ChildJson(
                    kind=child_kind(child),
                    text=child.text,
                    path=str(child_at.path),
                    line=child_at.line,
                )
            )
    return _DiagnosticJson(
        path=str(diagnostic.path),
        line=primary_line(diagnostic),
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


def _count(number: int, noun: str) -> str:
    """A count with its noun, pluralised with an `s` unless it is one.

    Args:
        number: How many there are.
        noun: What there are, in the singular.
    """
    if number == 1:
        return f'{number} {noun}'
    return f'{number} {noun}s'
