"""What a run of the rules reports: a diagnostic per occurrence, its severity, and the order diagnostics print in.

A diagnostic locates a rule's occurrence at the path of the subject it was found in, with the severity the rule
runs at. It holds the occurrence and copies none of its fields, so its code, message, labels, help and notes, and
specification reach any output through the occurrence alone.

The order is an output contract, total over one revision, so one revision always prints the same diagnostics in
the same order: by path, then primary location, then severity, then code, then message. `DiagnosticOrder` states
that order as the fields it compares, and `diagnostic_order` builds it as the sort key.

This module is the rules engine's report. `reporting` beside it is the per-check pipeline's, whose `Violation` and
`Finding` the `Diagnostic` here replaces; it stays until the command line runs the rules engine.
"""

from dataclasses import dataclass
from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import Rule, Severity
from lorecraft.rules.location import Here, WholeSubject


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One occurrence of a rule, located at the subject it was found in, with the severity it is reported at.

    Attributes:
        path: The subject the occurrence was found in.
        occurrence: The rule's occurrence, which renders the code, the message and everything around it.
        severity: The severity the occurrence is reported at.
    """

    path: RootRelativePath
    occurrence: Rule
    severity: Severity


@dataclass(frozen=True, slots=True, order=True)
class DiagnosticOrder:
    """Where a diagnostic sorts in a report; its fields compare in the order they are declared.

    Attributes:
        path: The subject's path as its POSIX string, compared by code point and never by locale, so `a-b/c.md`
            sorts before `a/b.md` and `B.md` before `a.md`.
        location: The primary location's rank: 0 for the whole subject, otherwise its line, so the whole subject
            sorts before every line.
        severity: The severity's rank: 0 for an error, 1 for a warning, so an error sorts first.
        code: The code as printed, such as `SMP002`, whose fixed-width digits keep numeric order within a group.
        message: The message text, so the order never depends on how a rule iterates.
    """

    path: str
    location: int
    severity: int
    code: str
    message: str


def diagnostic_order(diagnostic: Diagnostic) -> DiagnosticOrder:
    """The key that sorts diagnostics into their output order, as in `sorted(diagnostics, key=diagnostic_order)`.

    Args:
        diagnostic: The diagnostic to place.
    """
    primary = diagnostic.occurrence.primary()
    match primary:
        case WholeSubject():
            # Line numbers start at 1, so 0 places the whole subject before every line.
            location = 0
        case Here():
            location = primary.line.number
        case _:
            assert_never(primary)

    match diagnostic.severity:
        case Severity.ERROR:
            severity = 0
        case Severity.WARNING:
            severity = 1
        case _:
            assert_never(diagnostic.severity)

    return DiagnosticOrder(
        path=str(diagnostic.path),
        location=location,
        severity=severity,
        code=str(diagnostic.occurrence.CODE),
        message=diagnostic.occurrence.message(),
    )
