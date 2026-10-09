"""The parts of a diagnostic every output reads: its order, its primary line, its places and the marks drawn on them.

Pure: each function takes values a run returned and returns values, so the text, short and JSON outputs share one
reading of a diagnostic and never disagree about where it points.
"""

from dataclasses import dataclass
from typing import Literal, assert_never

from lorecraft.checks import Diagnostic, SubjectReport, diagnostic_order
from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
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


@dataclass(frozen=True, slots=True)
class Mark:
    """A place a diagnostic points at, drawn on the source in text output.

    Attributes:
        path: The file the mark is in.
        line: The line it points at, or None when it points at the whole of the file.
        text: What the mark says about the place; empty for a place a help or note points at, or the primary line
            of a diagnostic whose rule gives it no label.
        primary: True for the line the diagnostic is reported at, which text output underlines apart from the others.
    """

    path: RootRelativePath
    line: LineNumber | None
    text: str
    primary: bool


def ordered_diagnostics(reports: tuple[SubjectReport, ...]) -> list[Diagnostic]:
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


def primary_line(diagnostic: Diagnostic) -> LineNumber | None:
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


def place(subject: RootRelativePath, at: Here | Elsewhere) -> tuple[RootRelativePath, LineNumber | None]:
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


def child_place(
    subject: RootRelativePath, child: Subdiagnostic | EntrySubdiagnostic
) -> tuple[RootRelativePath | None, LineNumber | None]:
    """The file and the line a help or note points at; both None when it points nowhere.

    Args:
        subject: The path of the subject the diagnostic was found in, which a line of the subject is reported at.
        child: The help or note whose place is read.
    """
    if child.at is None:
        return None, None
    return place(subject, child.at)


def format_place(path: RootRelativePath, line: LineNumber | None) -> str:
    """A place as text: `path:line`, or the path alone for a whole file.

    Args:
        path: The file the place is in, printed as it is.
        line: The line the place points at in that file, or None when it points at the whole file.
    """
    if line is None:
        return str(path)
    return f'{path}:{line.number}'


def child_kind(child: Subdiagnostic | EntrySubdiagnostic) -> Literal['help', 'note']:
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


def diagnostic_marks(diagnostic: Diagnostic) -> list[Mark]:
    """The places a diagnostic points at, in the order they are drawn: its labels, then the places its notes name.

    The line the diagnostic is reported at is always marked: by its label if the rule gives one, and otherwise by a
    mark with no text. A help or note that points at a place already marked adds nothing.

    Args:
        diagnostic: The diagnostic whose labels and children are read.
    """
    subject = diagnostic.path
    occurrence = diagnostic.occurrence
    reported_at = primary_line(diagnostic)

    marks: list[Mark] = []
    for label in occurrence.labels():
        path, line = place(subject, label.at)
        is_primary = path == subject and line is not None and line == reported_at
        marks.append(Mark(path, line, label.text, is_primary))
    if reported_at is not None and not any(mark.primary for mark in marks):
        marks.insert(0, Mark(subject, reported_at, '', True))

    for child in occurrence.children():
        path, line = child_place(subject, child)
        if path is None:
            continue
        # A whole file is already pointed at by any mark in it.
        if any(mark.path == path and (line is None or mark.line == line) for mark in marks):
            continue
        marks.append(Mark(path, line, '', False))
    return marks
