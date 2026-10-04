"""What a run of the rules reports: a diagnostic per occurrence, the order they print in, and a report per subject.

A diagnostic locates an occurrence at the path of the subject it was found in, with the severity it is reported
at, and it comes in one of two kinds. A `RuleDiagnostic` holds a rule's occurrence at the severity the rule table
enables the rule at. An `EngineDiagnostic` holds an engine condition's occurrence, and reads its severity from the
condition's class rather than holding one, so it can never carry another. Either holds its occurrence and copies
none of its fields, so its code, message, labels, help and notes, and specification reach any output through the
occurrence alone.

The order is an output contract, total over one revision, so one revision always prints the same diagnostics in
the same order: by path, then primary location, then severity, then code, then message. `DiagnosticOrder` states
that order as the fields it compares, and `diagnostic_order` builds it as the sort key.

Each subject the runner checks, a document or a skill, gets one report, and either kind of report gives its
diagnostics as `diagnostics`. A `CheckedSubject` decoded, and holds its diagnostics, in their output order however
it is built, and the inputs no specification governs it for. An `UndecodableSubject` did not, so no rule judged it:
it holds only its ref, and its one diagnostic, the engine's, is built from that ref, at the subject's path.

This module is the rules engine's report. `reporting` beside it is the per-check pipeline's, whose `Violation` and
`Finding` the `Diagnostic` here replaces; it stays until the command line runs the rules engine.
"""

from dataclasses import dataclass
from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.document import DocumentRef
from lorecraft.project.skill import SkillRef
from lorecraft.rules.declaration import EngineCondition, Rule, Severity
from lorecraft.rules.engine.invalid_utf8 import InvalidUtf8
from lorecraft.rules.inputs import InputKind
from lorecraft.rules.location import Here, WholeSubject


@dataclass(frozen=True, slots=True)
class RuleDiagnostic:
    """One occurrence of a rule, located at the subject it was found in, at the severity the rule runs at.

    Attributes:
        path: The subject the occurrence was found in.
        occurrence: The rule's occurrence, which renders the code, the message and everything around it.
        severity: The severity the rule table enables the rule at.
    """

    path: RootRelativePath
    occurrence: Rule
    severity: Severity


@dataclass(frozen=True, slots=True)
class EngineDiagnostic:
    """One occurrence of an engine condition, located at the subject the engine found it in.

    Attributes:
        path: The subject the engine found the condition in.
        occurrence: The condition's occurrence, which renders the code, the message and everything around it.
    """

    path: RootRelativePath
    occurrence: EngineCondition

    @property
    def severity(self) -> Severity:
        """The severity the condition's class fixes as its `SEVERITY`; no configuration changes it."""
        return self.occurrence.SEVERITY


# One occurrence located at the subject it was found in, with the severity it is reported at: a rule's, at the
# severity the run enables the rule at, or an engine condition's, at the severity its class fixes.
type Diagnostic = RuleDiagnostic | EngineDiagnostic


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


# A subject the runner checks: a document, or a skill, whose report path is its `SKILL.md`.
type SubjectRef = DocumentRef | SkillRef


@dataclass(frozen=True, slots=True)
class CheckedSubject:
    """A subject that decoded, so the enabled rules judged every input it is governed for.

    Attributes:
        ref: The document or skill the rules judged; a skill's diagnostics are reported at its `SKILL.md`.
        diagnostics: Every occurrence the rules found in it, in the order `diagnostic_order` sorts them into,
            whatever order they are given in; empty when it holds to every rule.
        ungoverned: The input kinds an enabled rule reads that no specification governs the subject for, in the
            order the runner builds them; no rule over such an input judged the subject.
    """

    ref: SubjectRef
    diagnostics: tuple[Diagnostic, ...]
    ungoverned: tuple[InputKind, ...]

    def __post_init__(self) -> None:
        """Sort the diagnostics into their output order, so a report holds them in it however it is built."""
        # The record is frozen, and `object.__setattr__` is how a frozen dataclass sets its own field while it is
        # being constructed; nothing can set it after.
        object.__setattr__(self, 'diagnostics', tuple(sorted(self.diagnostics, key=diagnostic_order)))


@dataclass(frozen=True, slots=True)
class UndecodableSubject:
    """A subject whose file is not UTF-8, so no rule judged it; it reports the engine's one diagnostic.

    A skill's file is its `SKILL.md`.

    Attributes:
        ref: The document or skill whose file did not decode, and the path its diagnostic is reported at.
    """

    ref: SubjectRef

    @property
    def diagnostics(self) -> tuple[EngineDiagnostic]:
        """The subject's one diagnostic: `InvalidUtf8` at its path, which for a skill is its `SKILL.md`."""
        return (EngineDiagnostic(self.ref.path, InvalidUtf8()),)


# What the runner reports for one subject: what the rules found in it, or that it did not decode.
type SubjectReport = CheckedSubject | UndecodableSubject
