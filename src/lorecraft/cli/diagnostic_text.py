"""Draw the diagnostics of a run as text for a person, the way the established compilers draw theirs.

Pure: the subject reports and the source lines arrive as values, and the text comes back as a string, so nothing here
reads the disk, the terminal or the environment. The caller decides the `TextStyle`.

The diagnostics are printed in the order `diagnostic_order` states, an empty line between two of them. One diagnostic
reads, as `docs/arch/adr-010-diagnostics.md` lays it out:

    error[OUT006]: missing required section `Usage`
      --> docs/feat/cli-check.md:12
       │
    12 │ ## Options
       │ ────────── expected `Usage` before `Options`
       │
      ::: docs/__meta__/feat.structure.json
       │
       = note: the document structure is set here
       = help: describe how to invoke the command

- The header holds the severity, the code and the message; the `-->` line the line the diagnostic is reported at.
- Each labelled line of a file is excerpted from the source lines, with its label under it. The line the diagnostic
  is reported at is underlined with `─`, any other line of the same file with a dotted `┄`. Lines more than one apart
  are separated by an ellipsis. Every other file a label or a note points at follows under its own `:::` line.
- A subject without lines, such as a layout entry, prints its path and no excerpt.
- A place whose source is not at hand prints its label as an `= at` line instead of an excerpt.
- The help and notes follow as `=` lines, aligned under their first line. A one-line text is wrapped to the
  terminal width; a text of several lines, such as a sample, is drawn line for line.
- Where the output cannot carry Unicode, `│ ─ ┄ …` become `| ^ - .`.
"""

import textwrap
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, assert_never

import typer

from lorecraft.checks import Diagnostic, SubjectReport
from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.declaration import Severity
from lorecraft.rules.location import EntrySubdiagnostic, Subdiagnostic

from .diagnostic_parts import (
    Mark,
    child_kind,
    diagnostic_marks,
    format_place,
    ordered_diagnostics,
    primary_line,
)

# The decoded lines of every file a diagnostic of the run excerpts, by path, without their line breaks.
type SourceLines = Mapping[RootRelativePath, tuple[str, ...]]

# A tab in a source line is drawn as this many spaces, so an underline sits under the text it labels.
_TAB_WIDTH: Final[int] = 4
# A help or note is never wrapped narrower than this, however deep its prefix or small the terminal.
_MIN_NOTE_WIDTH: Final[int] = 20


@dataclass(frozen=True, slots=True)
class TextStyle:
    """How the text is drawn, decided by the caller from the terminal it prints to.

    Attributes:
        color: True to emphasise with ANSI escape sequences.
        unicode: True to draw with box-drawing characters, False for an ASCII fallback.
        width: The columns a line may use; a help or note is wrapped to it.
    """

    color: bool
    unicode: bool
    width: int


@dataclass(frozen=True, slots=True)
class _Glyphs:
    """The characters the excerpt is drawn with.

    Attributes:
        gutter: The vertical line between the line numbers and the source.
        primary: What underlines the line the diagnostic is reported at.
        secondary: What underlines any other labelled line.
        elision: What stands for the lines left out between two excerpted ones.
    """

    gutter: str
    primary: str
    secondary: str
    elision: str


_UNICODE_GLYPHS: Final[_Glyphs] = _Glyphs(gutter='│', primary='─', secondary='┄', elision='…')
_ASCII_GLYPHS: Final[_Glyphs] = _Glyphs(gutter='|', primary='^', secondary='-', elision='.')


def render_text(reports: tuple[SubjectReport, ...], sources: SourceLines, style: TextStyle) -> str:
    """Every diagnostic of the run as text, in the order `diagnostic_order` sorts them into.

    Args:
        reports: One report per subject the run checked, in any order.
        sources: The lines of each file a diagnostic excerpts; a file missing from it is drawn without an excerpt.
        style: How to draw: with colour or without, with Unicode or ASCII, and how wide.

    Returns:
        The diagnostics, an empty line between two of them, as the established compilers separate theirs; no
        trailing newline, and empty when the run found nothing.
    """
    blocks: list[str] = []
    for diagnostic in ordered_diagnostics(reports):
        blocks.append('\n'.join(_diagnostic_lines(diagnostic, sources, style)))
    return '\n\n'.join(blocks)


def _diagnostic_lines(diagnostic: Diagnostic, sources: SourceLines, style: TextStyle) -> list[str]:
    """The lines one diagnostic is drawn as: its header, the files it points at, then its help and notes.

    Args:
        diagnostic: The diagnostic to draw.
        sources: The lines of each file that can be excerpted.
        style: How to draw.
    """
    occurrence = diagnostic.occurrence
    severity = diagnostic.severity.value
    header = _paint(style, f'{severity}[{occurrence.CODE}]', fg=_severity_color(diagnostic.severity), bold=True)
    lines = [header + _paint(style, f': {occurrence.message()}', bold=True)]

    marks = diagnostic_marks(diagnostic)
    width = _gutter_width(marks, sources)
    # The unlabelled lines the gutter and the `=` lines are drawn under.
    lead = ' ' * (width + 1)
    glyphs = _UNICODE_GLYPHS if style.unicode else _ASCII_GLYPHS
    blank_gutter = lead + _paint(style, glyphs.gutter, fg='blue', bold=True)

    for index, (path, group) in enumerate(_group_by_file(diagnostic.path, marks)):
        arrow = '-->' if index == 0 else ':::'
        reported_at = primary_line(diagnostic) if index == 0 else _first_line(group)
        lines.append(f'{" " * width}{_paint(style, arrow, fg="blue", bold=True)} {format_place(path, reported_at)}')

        # A label whose source is not at hand is told under the place it is in, with no excerpt.
        excerpted: list[Mark] = []
        for mark in group:
            if _has_source(mark, sources):
                excerpted.append(mark)
            elif mark.text:
                equals = _paint(style, '=', fg='blue', bold=True)
                lines.append(f'{lead}{equals} at {format_place(mark.path, mark.line)}: {mark.text}')
        if excerpted:
            lines.append(blank_gutter)
            lines.extend(_excerpt_lines(excerpted, sources[path], width, diagnostic.severity, style, glyphs))
            lines.append(blank_gutter)
        elif index > 0:
            # A pointer to another file is set apart from what follows it by the gutter, as the excerpt would be.
            lines.append(blank_gutter)

    for child in occurrence.children():
        lines.extend(_child_lines(child, lead, style))
    # The gutter that closes an excerpt only separates it from what follows.
    if lines[-1] == blank_gutter:
        lines.pop()
    return lines


def _group_by_file(subject: RootRelativePath, marks: list[Mark]) -> list[tuple[RootRelativePath, list[Mark]]]:
    """The marks grouped by the file they are in: the subject's first, then each other file as it first appears.

    The subject's group is always there, so a diagnostic with no mark in its own file still names it. A group's
    marks are in line order, the whole file first.

    Args:
        subject: The path of the subject the diagnostic was found in.
        marks: Every mark of the diagnostic.
    """
    groups: dict[RootRelativePath, list[Mark]] = {subject: []}
    for mark in marks:
        groups.setdefault(mark.path, []).append(mark)
    return [(path, sorted(group, key=_line_order)) for path, group in groups.items()]


def _line_order(mark: Mark) -> int:
    """Where a mark sorts in its file: the whole file, which has no line, before every line.

    Args:
        mark: The mark to place.
    """
    if mark.line is None:
        return 0
    return mark.line.number


def _first_line(group: list[Mark]) -> LineNumber | None:
    """The first line any mark of a file points at, or None when none points at a line.

    Args:
        group: The marks of one file, in line order.
    """
    for mark in group:
        if mark.line is not None:
            return mark.line
    return None


def _has_source(mark: Mark, sources: SourceLines) -> bool:
    """True when the line a mark points at can be excerpted.

    Args:
        mark: The mark to excerpt.
        sources: The lines of each file that can be excerpted.
    """
    if mark.line is None:
        return False
    lines = sources.get(mark.path)
    return lines is not None and mark.line.number <= len(lines)


def _gutter_width(marks: list[Mark], sources: SourceLines) -> int:
    """The columns the line numbers of the excerpts take: the digits of the greatest line number excerpted, at least 1.

    Args:
        marks: Every mark of the diagnostic.
        sources: The lines of each file that can be excerpted.
    """
    width = 1
    for mark in marks:
        if mark.line is not None and _has_source(mark, sources):
            width = max(width, len(str(mark.line.number)))
    return width


def _excerpt_lines(
    marks: list[Mark],
    source: tuple[str, ...],
    width: int,
    severity: Severity,
    style: TextStyle,
    glyphs: _Glyphs,
) -> list[str]:
    """The numbered source lines of one file that carry a mark, each followed by an underline per mark.

    Args:
        marks: The marks to draw, in line order, each on a line of the source.
        source: The lines of the file.
        width: The columns the line numbers take.
        severity: The severity of the diagnostic, which colours the underline of the line it is reported at.
        style: How to draw.
        glyphs: The characters to draw with.
    """
    marks_by_line: dict[int, list[Mark]] = {}
    for mark in marks:
        if mark.line is not None:
            marks_by_line.setdefault(mark.line.number, []).append(mark)

    lines: list[str] = []
    previous: int | None = None
    for number, line_marks in marks_by_line.items():
        if previous is not None:
            hidden = number - previous - 1
            if hidden == 1:
                lines.append(_source_line(previous + 1, source, width, style, glyphs))
            elif hidden > 1:
                lines.append(_paint(style, f'{glyphs.elision:>{width}} {glyphs.gutter}', fg='blue', bold=True))
        lines.append(_source_line(number, source, width, style, glyphs))
        text = source[number - 1].expandtabs(_TAB_WIDTH).rstrip()
        # The line the diagnostic is reported at is underlined before any other line's label.
        for mark in sorted(line_marks, key=lambda mark: not mark.primary):
            lines.append(_underline(mark, text, width, severity, style, glyphs))
        previous = number
    return lines


def _source_line(number: int, source: tuple[str, ...], width: int, style: TextStyle, glyphs: _Glyphs) -> str:
    """One numbered line of the source, in the gutter.

    Args:
        number: The one-based number of the line.
        source: The lines of the file.
        width: The columns the line numbers take.
        style: How to draw.
        glyphs: The characters to draw with.
    """
    gutter = _paint(style, f'{number:>{width}} {glyphs.gutter}', fg='blue', bold=True)
    return f'{gutter} {source[number - 1].expandtabs(_TAB_WIDTH)}'.rstrip()


def _underline(mark: Mark, text: str, width: int, severity: Severity, style: TextStyle, glyphs: _Glyphs) -> str:
    """The line under a source line that underlines the text of it and says what the mark labels.

    The underline spans the line's text, from its first character that is not a blank to its last; a blank line is
    marked by one character.

    Args:
        mark: The mark to draw.
        text: The source line the mark is on, with its tabs expanded and its trailing blanks gone.
        width: The columns the line numbers take.
        severity: The severity of the diagnostic.
        style: How to draw.
        glyphs: The characters to draw with.
    """
    start = len(text) - len(text.lstrip())
    end = len(text)
    if end <= start:
        start, end = 0, 1
    if mark.primary:
        glyph, color = glyphs.primary, _severity_color(severity)
    else:
        glyph, color = glyphs.secondary, 'blue'

    gutter = _paint(style, f'{" " * (width + 1)}{glyphs.gutter}', fg='blue', bold=True)
    underline = _paint(style, glyph * (end - start), fg=color, bold=True)
    label = ''
    if mark.text:
        label = ' ' + _paint(style, mark.text, fg=color, bold=True)
    return f'{gutter} {" " * start}{underline}{label}'


def _child_lines(child: Subdiagnostic | EntrySubdiagnostic, lead: str, style: TextStyle) -> list[str]:
    """The lines one help or note is drawn as, its kind on the first and its text aligned under itself.

    Args:
        child: The help or note to draw; a text of one line is wrapped to the width, and each line of a longer one
            becomes one output line, unwrapped. A trailing line break adds none, and a CRLF break counts as one.
        lead: The blanks that put the `=` under the gutter.
        style: How to draw.
    """
    kind = child_kind(child)
    prefix = f'{lead}= {kind}: '
    indent = ' ' * len(prefix)
    available = max(style.width - len(prefix), _MIN_NOTE_WIDTH)

    # `splitlines` rather than `split('\n')`: it drops the empty piece after a trailing line break and the `\r` of a
    # CRLF one. A text with no lines at all still draws its prefix.
    text_lines = child.text.splitlines() or ['']
    wrapped: list[str] = []
    if len(text_lines) == 1:
        wrapped.extend(_wrap(text_lines[0].rstrip(), available))
    else:
        # A text of several lines is a sample, such as a list, a table or code: breaking a line of it would change
        # what it says, so each line is drawn as it is, however far it runs.
        wrapped.extend(line.rstrip() for line in text_lines)

    painted_prefix = f'{lead}{_paint(style, "=", fg="blue", bold=True)} {_paint(style, f"{kind}:", bold=True)} '
    lines = [f'{painted_prefix}{wrapped[0]}'.rstrip()]
    for content in wrapped[1:]:
        # Leading indentation is kept, so a sample's nesting survives; a blank line stays empty.
        lines.append(f'{indent}{content}' if content else '')
    return lines


def _wrap(line: str, width: int) -> list[str]:
    """One line of a help or note broken at blanks to fit the width, its indentation kept on every piece.

    A line that fits, and a blank one, are returned as they are; a word longer than the width is not broken.

    Args:
        line: The line, without trailing blanks.
        width: The columns a piece may use, its indentation included.
    """
    if len(line) <= width:
        return [line]
    indentation = line[: len(line) - len(line.lstrip())]
    return textwrap.wrap(
        line.strip(),
        width=width,
        initial_indent=indentation,
        subsequent_indent=indentation,
        break_long_words=False,
        break_on_hyphens=False,
    )


def _severity_color(severity: Severity) -> str:
    """The colour a severity is drawn in: red for an error, yellow for a warning.

    Args:
        severity: The severity of a diagnostic.
    """
    match severity:
        case Severity.ERROR:
            return 'red'
        case Severity.WARNING:
            return 'yellow'
        case _:
            assert_never(severity)


def _paint(style: TextStyle, text: str, *, fg: str | None = None, bold: bool = False) -> str:
    """The text wrapped in the escape sequences of the colour and weight, or as it is when the style has no colour.

    Args:
        style: How to draw.
        text: The text to emphasise.
        fg: The colour, one of the names `typer.style` takes; None leaves the colour as it is.
        bold: True to make the text bold.
    """
    if not style.color or not text:
        return text
    return typer.style(text, fg=fg, bold=bold)
