"""What a run of the rules reports: a diagnostic per occurrence, the order they print in, and a report per subject.

A diagnostic locates an occurrence at the path of the subject it was found in, with the severity it is reported
at, and it comes in one of two kinds. A `RuleDiagnostic` holds a rule's occurrence at the severity the rule table
enables the rule at. An `EngineDiagnostic` holds an engine condition's occurrence, and reads its severity from the
condition's class rather than holding one, so it can never carry another. Either holds its occurrence and copies
none of its fields, so its code, message, labels, help and notes, and meta spec reach any output through the
occurrence alone.

The order is an output contract, total over one revision, so one revision always prints the same diagnostics in
the same order: by path, then primary location, then severity, then code, then message. `DiagnosticOrder` states
that order as the fields it compares, and `diagnostic_order` builds it as the sort key.

Each subject the runner checks, a document, a meta specification, a skill or a skill's resource, gets one report,
and either kind of report gives its diagnostics as `diagnostics`. A `CheckedItem` decoded, and holds its
diagnostics, in their output order however it is built, and the specification facets no meta spec governs it for.
A skill entry has package checks independent of corpus governance, while a resource has no meta-spec structure
governance. An
`UndecodableSubject` did not decode,
so no rule judged it: it holds its ref and where the bytes stopped being UTF-8, and its one diagnostic, the engine's,
is built from them, at the subject's path. An `UnreadableDocument` could not be read at all, so it holds its document
or specification ref and the engine's unreadable-path condition, and counts as a subject. A layout
entry, one symlink of the skill layout whose chain leaves the repository or a directory under `docs/` named like a
reserved corpus, has no text to decode and no meta spec to be
ungoverned by, so it gets a report of its own, a `CheckedLayoutEntry`: its path and its diagnostics, in their output
order.

Two reports come from what failed to load, never from a rule. A `SkippedSubject` is a document decoded and not judged,
because a structure file that governs it failed to load, or a skill alias whose docs target was refused: it holds no
diagnostic and is listed in coverage with the paths that caused it. A `LoadFailureReport` is the failure itself,
filed at its own path with the one diagnostic of its engine condition, whatever the configuration and the selection,
in the same total order as every other diagnostic.
"""

from dataclasses import dataclass
from typing import assert_never

from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.document import DocumentRef, SpecRef
from lorecraft.project.item import MarkdownItemRef
from lorecraft.project.skill import SkillAliasRef, SkillRef, SkillResourceRef
from lorecraft.rules.engine.invalid_utf8 import InvalidUtf8
from lorecraft.vfs import Utf8Failure

from .declaration import EngineCondition, Rule
from .identity import Severity
from .location import Here, WholeSubject
from .subject import Facet


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
    location: UnsignedInt
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
            location = UnsignedInt(0)
        case Here():
            location = primary.line.as_unsigned()
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


# A subject the runner checks: a document, a meta specification, a skill, whose report path is its `SKILL.md`, or a
# skill's resource, whose report path is where an agent reaches it.
type SubjectRef = DocumentRef | SkillRef | SkillResourceRef | SkillAliasRef | SpecRef


@dataclass(frozen=True, slots=True)
class CheckedItem:
    """A Markdown item that decoded, so the enabled rules judged everything it is governed for.

    A document, a skill's `SKILL.md` and a skill's resource are reported alike. Only a rule over a document is gated
    on a specification facet beyond the checks the package always activates for a skill file, so a skill file's
    report holds no ungoverned facet by construction, and only a document's can.

    Attributes:
        ref: The item the rules judged, at the path its diagnostics are reported at.
        diagnostics: Every occurrence the rules found in it, in the order `diagnostic_order` sorts them into,
            whatever order they are given in; empty when it holds to every rule.
        ungoverned: The specification facets an enabled rule reads that no meta spec governs the item for, in the order
            the runner reads them; no rule that reads one judged the item.
    """

    ref: MarkdownItemRef
    diagnostics: tuple[Diagnostic, ...]
    ungoverned: tuple[Facet, ...] = ()

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
        ref: The document, specification, skill or resource whose file did not decode, and the path its diagnostic
            is reported at.
        failure: Where the file's bytes first stop being UTF-8, and why.
    """

    ref: SubjectRef
    failure: Utf8Failure

    @property
    def diagnostics(self) -> tuple[EngineDiagnostic]:
        """The subject's one diagnostic: `InvalidUtf8` at its path, which for a skill is its `SKILL.md`."""
        return (EngineDiagnostic(self.ref.path, InvalidUtf8(failure=self.failure)),)


@dataclass(frozen=True, slots=True)
class UnreadableDocument:
    """A governed document or meta specification that could not be read, still counted as a subject with its `LC002`.

    Attributes:
        ref: The document or specification whose bytes the snapshot could not read.
        occurrence: The engine condition explaining the unreadable path.
    """

    ref: DocumentRef | SpecRef
    occurrence: EngineCondition

    @property
    def diagnostics(self) -> tuple[EngineDiagnostic]:
        """The unreadable-path diagnostic at the document's path."""
        return (EngineDiagnostic(self.ref.path, self.occurrence),)


@dataclass(frozen=True, slots=True)
class CheckedLayoutEntry:
    """A layout entry the enabled rules judged.

    It is either a symlink of the skill layout whose chain leaves the repository or a directory under `docs/` named
    like a reserved corpus. The entry has no text, so it is never undecodable, and the package governs the layout, so
    it is never ungoverned.

    Attributes:
        path: Where the entry is reached, the path its diagnostics are reported at. For a symlink: a skills directory
            as declared, an entry in one, that entry's `SKILL.md`, or a path inside a skill, under the skill's entry.
            For a directory: its path under `docs/`.
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


@dataclass(frozen=True, slots=True)
class SkippedSubject:
    """A document or skill alias no rule judged because a path it depends on could not be read.

    A document governed by a failed structure layer cannot be called clean from the layers that loaded. A skill file
    whose resolved target was refused cannot be judged either. A refused directory alias is reported at its alias
    path, while its owning skill remains a separate subject. It is coverage, never a diagnostic: it holds none, and
    the failure that caused it is reported once, at its own path, as a `LoadFailureReport`.

    Attributes:
        ref: The document, skill or alias path that was not judged.
        failed_layers: Paths of failed structure layers or refused docs targets that prevented checking.
    """

    ref: SubjectRef
    failed_layers: tuple[RootRelativePath, *tuple[RootRelativePath, ...]]

    @property
    def diagnostics(self) -> tuple[()]:
        """None: the subject was not judged, and the failure is reported at its own path."""
        return ()


@dataclass(frozen=True, slots=True)
class LoadFailureReport:
    """One unit of the declaration that failed to load, reported once at its own path.

    It is a report of its own, beside the subjects', filed at the structure file, the directory or the skill entry
    that failed, and not once per subject the failure touches.

    Attributes:
        path: Where the declaration reaches the unit that failed: the path its diagnostic is reported at.
        occurrence: The engine condition the failure is, which renders the code, the message and everything around it.
    """

    path: RootRelativePath
    occurrence: EngineCondition

    @property
    def diagnostics(self) -> tuple[EngineDiagnostic]:
        """The failure's one diagnostic: the condition at its path."""
        return (EngineDiagnostic(self.path, self.occurrence),)


# What the runner reports for one subject: what the rules found in it, that it did not decode, what they found at a
# layout entry, or that a failed layer of a meta spec kept them from judging a document.
type SubjectReport = CheckedItem | UndecodableSubject | UnreadableDocument | CheckedLayoutEntry | SkippedSubject

# What a run hands its output: a report per subject, and one per unit of the declaration that failed to load, which is
# no subject and is filed at its own path.
type RunReport = SubjectReport | LoadFailureReport
