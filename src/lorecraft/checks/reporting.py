"""Shared findings and output formatting for document checks.

A check returns violations: where in the document a rule is broken, but not which document, since a check is a
pure function of what it reads and never needs the document's path. The run that checked a document knows which
it was, and ``Finding.at`` joins the two into a finding, the located form the output prints.

A violation may carry notes, the way a compiler diagnostic does: help on how to fix it, or a note adding context
such as an example. They stay apart from the message, so the message still states the broken rule on one line.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Self

from lorecraft.core.path import RootRelativePath
from lorecraft.project.syntax import LineNumber


class NoteKind(Enum):
    """What a note on a violation offers; the value is the label the output prints before its text."""

    HELP = 'help'
    """How to fix the violation."""
    NOTE = 'note'
    """Context that explains the violation, such as an example of what was expected."""


@dataclass(frozen=True, slots=True)
class Note:
    """One note attached to a violation, printed under its message.

    Attributes:
        kind: Whether the note is help or context; its value is the label printed before `text`.
        text: What the note says; it may span several lines.
    """

    kind: NoteKind
    text: str


@dataclass(frozen=True, slots=True)
class Violation:
    """One broken rule in one document, without the document's path.

    Attributes:
        line: Where the violation is reported; line 1 when it concerns the whole document rather than one line.
        rule: Stable identifier for the violated rule.
        message: Human-readable explanation of the violation.
        spec: The specification file that states the broken rule, or None, the default, for a rule the check
            itself holds, such as a document that is not UTF-8.
        notes: Help and context for the reader, in the order they print; none, the default, for most rules.
    """

    line: LineNumber
    rule: str
    message: str
    spec: RootRelativePath | None = None
    notes: tuple[Note, ...] = ()


@dataclass(frozen=True, slots=True)
class Finding:
    """One validation finding, located in a repository document; frozen, so findings compare and hash by value.

    Attributes:
        path: The affected document; turned into text only where a finding is printed or serialised.
        line: The line containing the finding.
        rule: Stable identifier for the violated rule.
        message: Human-readable explanation of the finding.
        spec: The specification file that states the broken rule, or None for a rule the check itself holds.
        notes: Help and context for the reader, in the order they print; may be empty.
    """

    path: RootRelativePath
    line: LineNumber
    rule: str
    message: str
    spec: RootRelativePath | None = None
    notes: tuple[Note, ...] = ()

    @classmethod
    def at(cls, path: RootRelativePath, violation: Violation) -> Self:
        """The finding a violation is, in the document at `path`.

        Args:
            path: The document the violation was found in, which the violation itself does not carry.
            violation: The broken rule whose line, rule, message, specification and notes the finding copies.
        """
        return cls(
            path=path,
            line=violation.line,
            rule=violation.rule,
            message=violation.message,
            spec=violation.spec,
            notes=violation.notes,
        )


def format_finding(finding: Finding) -> str:
    """Format one finding for text output: `<path>:<line>: [<rule>] <message>`, then each of its notes.

    A note prints as `  = <kind>: <text>`, the way rustc prints one. Every later line of its text is indented to
    start under the first, and a blank line prints empty, with no trailing whitespace.

    Args:
        finding: The finding to print; one line when it has no notes, with no trailing newline.
    """
    lines = [f'{finding.path}:{finding.line}: [{finding.rule}] {finding.message}']
    for note in finding.notes:
        lines.extend(_format_note(note))
    return '\n'.join(lines)


def _format_note(note: Note) -> list[str]:
    """The lines one note prints as, its label on the first and its text aligned under itself.

    Args:
        note: The note to print; each line of its text becomes one output line, a trailing line break adds none,
            and a CRLF break counts as one.
    """
    label = f'  = {note.kind.value}: '
    indent = ' ' * len(label)
    # `splitlines` rather than `split('\n')`: it drops the empty piece after a trailing line break and the `\r` of a
    # CRLF one. A text with no lines at all still prints its label.
    first, *rest = note.text.splitlines() or ['']
    # Trailing whitespace is stripped from every line, which leaves a whitespace-only line empty; leading
    # indentation is kept, so a sample's nesting survives.
    lines = [f'{label}{first}'.rstrip()]
    for line in rest:
        content = line.rstrip()
        if content:
            lines.append(f'{indent}{content}')
        else:
            lines.append('')
    return lines
