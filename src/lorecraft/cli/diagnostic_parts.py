"""The parts of a diagnostic every output reads: its order, its primary line, its places and the marks drawn on them.

Pure: each function takes values a run returned and returns values, so the text, short and JSON outputs share one
reading of a diagnostic and never disagree about where it points.
"""

from dataclasses import dataclass
from typing import Literal, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.core.text import NonEmptyStr
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
from lorecraft.rules.report import Diagnostic, RunReport, diagnostic_order


@dataclass(frozen=True, slots=True)
class FilePlace:
    """A file a diagnostic, label, help or note points at, and the line of it when it points at one.

    Attributes:
        path: The file the place is in.
        line: The line it points at, or None when it points at the whole of the file.
    """

    path: RootRelativePath
    line: LineNumber | None


@dataclass(frozen=True, slots=True)
class LineMark:
    """A line a diagnostic points at, drawn on the source in text output.

    Attributes:
        path: The file the mark is in.
        line: The line it points at.
        text: A non-empty label for the line, or None when it has no label.
    """

    path: RootRelativePath
    line: LineNumber
    text: NonEmptyStr | None

    @property
    def place(self) -> FilePlace:
        """The file and line the mark is on."""
        return FilePlace(self.path, self.line)


@dataclass(frozen=True, slots=True)
class PrimaryLineMark:
    """The line a diagnostic is reported at, drawn apart from its other marks in text output.

    Attributes:
        path: The file the mark is in.
        line: The line it points at.
        text: A non-empty label for the line, or None when it has no label.
    """

    path: RootRelativePath
    line: LineNumber
    text: NonEmptyStr | None

    @property
    def place(self) -> FilePlace:
        """The file and line the mark is on."""
        return FilePlace(self.path, self.line)


@dataclass(frozen=True, slots=True)
class WholeFileMark:
    """A whole file a diagnostic points at, named in text output but never excerpted, so it is never the primary line.

    Attributes:
        path: The file the mark points at.
        text: What the mark says about the file; empty for a file a help or note points at.
    """

    path: RootRelativePath
    text: str

    @property
    def place(self) -> FilePlace:
        """The file the mark is on, with no line."""
        return FilePlace(self.path, None)


type Mark = LineMark | PrimaryLineMark | WholeFileMark


def ordered_diagnostics(reports: tuple[RunReport, ...]) -> list[Diagnostic]:
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


def place(subject: RootRelativePath, at: Here | Elsewhere) -> FilePlace:
    """The file and the line a location names; the line is None for the whole of another file.

    Args:
        subject: The path of the subject the diagnostic was found in, which `Here` names a line of.
        at: Where a label, help or note points: a line of the subject, or another file or a line in it.
    """
    match at:
        case Here():
            return FilePlace(subject, at.line)
        case Elsewhere():
            return FilePlace(at.path, at.line)
        case _:
            assert_never(at)


def child_place(subject: RootRelativePath, child: Subdiagnostic | EntrySubdiagnostic) -> FilePlace | None:
    """The file and the line a help or note points at, or None when it points nowhere.

    Args:
        subject: The path of the subject the diagnostic was found in, which a line of the subject is reported at.
        child: The help or note whose place is read.
    """
    if child.at is None:
        return None
    return place(subject, child.at)


def format_place(at: FilePlace) -> str:
    """A place as text: `path:line`, or the path alone for a whole file.

    Args:
        at: The place to print, its path as it is.
    """
    if at.line is None:
        return str(at.path)
    return f'{at.path}:{at.line}'


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
    primary_marked = False
    for label in occurrence.labels():
        at = place(subject, label.at)
        if at.line is None:
            marks.append(WholeFileMark(at.path, label.text))
            continue
        is_primary = at.path == subject and at.line == reported_at
        primary_marked = primary_marked or is_primary
        if is_primary:
            marks.append(PrimaryLineMark(at.path, at.line, _non_empty_label(label.text)))
        else:
            marks.append(LineMark(at.path, at.line, _non_empty_label(label.text)))
    if reported_at is not None and not primary_marked:
        marks.insert(0, PrimaryLineMark(subject, reported_at, None))

    for child in occurrence.children():
        at = child_place(subject, child)
        if at is None:
            continue
        # A whole file is already pointed at by any mark in it.
        if any(_already_points_at(mark, at) for mark in marks):
            continue
        if at.line is None:
            marks.append(WholeFileMark(at.path, ''))
        else:
            marks.append(LineMark(at.path, at.line, None))
    return marks


def _already_points_at(mark: Mark, at: FilePlace) -> bool:
    """True when a mark already points at a place: the same line of its file, or any mark at all for a whole file.

    Args:
        mark: A mark of the diagnostic.
        at: The place a help or note points at.
    """
    if mark.path != at.path:
        return False
    if at.line is None:
        return True
    match mark:
        case LineMark() | PrimaryLineMark():
            return mark.line == at.line
        case WholeFileMark():
            return False
        case _:
            assert_never(mark)


def _non_empty_label(text: str) -> NonEmptyStr | None:
    """Return a non-empty label value, or None for an empty label."""
    if not text:
        return None
    return NonEmptyStr.parse(text)
