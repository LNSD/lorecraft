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

Each subject the runner checks, a document, a skill or a skill's resource, gets one report, and either kind of
report gives its diagnostics as `diagnostics`. A `CheckedSubject` decoded, and holds its diagnostics, in their output
order however it is built, and the facets no specification governs it for. An `UndecodableSubject` did
not, so no rule judged it: it holds only its ref, and its one diagnostic, the engine's, is built from that ref, at the
subject's path. A layout entry, one symlink of the skill layout whose chain leaves the repository, has no text to
decode and no specification to be ungoverned by, so it gets a report of its own, a `CheckedLayoutEntry`: its path
and its diagnostics, in their output order.
"""

from dataclasses import dataclass
from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.document import DocumentRef
from lorecraft.project.skill import SkillRef, SkillResourceRef
from lorecraft.rules.declaration import EngineCondition, Rule, Severity
from lorecraft.rules.engine.invalid_utf8 import InvalidUtf8
from lorecraft.rules.location import Here, WholeSubject
from lorecraft.rules.subject import Facet


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


# A subject the runner checks: a document, a skill, whose report path is its `SKILL.md`, or a skill's resource, whose
# report path is where an agent reaches it.
type SubjectRef = DocumentRef | SkillRef | SkillResourceRef


@dataclass(frozen=True, slots=True)
class CheckedSubject:
    """A subject that decoded, so the enabled rules judged everything it is governed for.

    Attributes:
        ref: The document, skill or resource the rules judged; a skill's diagnostics are reported at its `SKILL.md`,
            and a resource's where an agent reaches it.
        diagnostics: Every occurrence the rules found in it, in the order `diagnostic_order` sorts them into,
            whatever order they are given in; empty when it holds to every rule.
        ungoverned: The facets an enabled rule reads that no specification governs the subject for, in the order the
            runner reads them; no rule that reads one judged the subject.
    """

    ref: SubjectRef
    diagnostics: tuple[Diagnostic, ...]
    ungoverned: tuple[Facet, ...]

    def __post_init__(self) -> None:
        """Sort the diagnostics into their output order, so a report holds them in it however it is built."""
        # The record is frozen, and `object.__setattr__` is how a frozen dataclass sets its own field while it is
        # being constructed; nothing can set it after.
        object.__setattr__(self, 'diagnostics', tuple(sorted(self.diagnostics, key=diagnostic_order)))


@dataclass(frozen=True, slots=True)
class UndecodableSubject:
    """A subject whose file is not UTF-8, so no rule judged it; it reports the engine's one diagnostic.

    A skill's file is its `SKILL.md`, and a resource's is reported where an agent reaches it.

    Attributes:
        ref: The document, skill or resource whose file did not decode, and the path its diagnostic is reported at.
    """

    ref: SubjectRef

    @property
    def diagnostics(self) -> tuple[EngineDiagnostic]:
        """The subject's one diagnostic: `InvalidUtf8` at its path, which for a skill is its `SKILL.md`."""
        return (EngineDiagnostic(self.ref.path, InvalidUtf8()),)


@dataclass(frozen=True, slots=True)
class CheckedLayoutEntry:
    """A layout entry the enabled rules judged: one symlink of the skill layout whose chain leaves the repository.

    The entry has no text, so it is never undecodable, and the package governs the skill layout, so it is never
    ungoverned.

    Attributes:
        path: Where an agent reaches the symlink, the path its diagnostics are reported at: a skills directory as
            declared, an entry in one, that entry's `SKILL.md`, or a path inside a skill, under the skill's entry.
        diagnostics: Every occurrence the rules found at the entry, in the order `diagnostic_order` sorts them into,
            whatever order they are given in.
    """

    path: RootRelativePath
    diagnostics: tuple[Diagnostic, ...]

    def __post_init__(self) -> None:
        """Sort the diagnostics into their output order, so a report holds them in it however it is built."""
        # The record is frozen, and `object.__setattr__` is how a frozen dataclass sets its own field while it is
        # being constructed; nothing can set it after.
        object.__setattr__(self, 'diagnostics', tuple(sorted(self.diagnostics, key=diagnostic_order)))


# What the runner reports for one subject: what the rules found in it, that it did not decode, or what they found at
# a layout entry.
type SubjectReport = CheckedSubject | UndecodableSubject | CheckedLayoutEntry
