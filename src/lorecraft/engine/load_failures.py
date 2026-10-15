"""What a run reports for the units of the declaration that failed to load: one report per failure, at its own path.

The one exception is a `docs/` or `docs/__meta__/` that cannot be listed: it comes back as the `UnlistableRoot` the
command stops the run on, and no report is made for it.

The model records each failure as plain facts and decides no policy (adr-015). This is where a failure becomes
what a run reports: the engine condition of its kind, in a `LoadFailureReport` filed at the failure's path, so a
failure is reported once, at its origin, whatever it touches and whatever the configuration and the selection.

A condition and the record that stands for it are declared apart, in `lorecraft.rules.engine` and in
`lorecraft.project.workspace`, and often share a name; the records are read as `workspace.<Record>` and each condition
as `<module>.<Condition>`, so the two are never confused.
"""

from dataclasses import dataclass
from typing import assert_never

from lorecraft.project import workspace
from lorecraft.rules.declaration import EngineCondition
from lorecraft.rules.engine import (
    RefusedOperation,
    invalid_utf8,
    malformed_structure_file,
    unreadable_path,
    unusable_structure_file,
)
from lorecraft.rules.engine.unreadable_path import NotARegularFile, Refused
from lorecraft.rules.report import LoadFailureReport


@dataclass(frozen=True, slots=True)
class UnlistableRoot:
    """A `docs/` or `docs/__meta__/` the model could not list, which no report stands for: the command stops the run.

    With neither a corpus nor a meta spec known, a report over what remained would read as a clean result for a
    workspace that was never checked.

    Attributes:
        failure: The first such failure the model listed.
    """

    failure: workspace.LoadFailure


type LoadFailureReports = tuple[LoadFailureReport, ...]
"""One report per load failure the model listed, each filed at the failure's own path."""


def report_load_failures(model: workspace.WorkspaceModel) -> UnlistableRoot | LoadFailureReports:
    """One report per load failure the model lists, each filed at the failure's path; the model lists each once.

    A `docs/` or `docs/__meta__/` that cannot be listed has no report: the result is that failure instead, for the
    command to stop on before it selects any subject.

    Args:
        model: The workspace model of the revision; its failures are plain data, so nothing here reads the disk.
    """
    reports: list[LoadFailureReport] = []
    for failure in model.load_failures:
        occurrence = _occurrence_of(failure)
        match occurrence:
            case UnlistableRoot():
                return occurrence
            case EngineCondition():
                # Every engine condition is reported the same way, whichever it is: filed at the failure's path.
                reports.append(LoadFailureReport(failure.path, occurrence))
            case _:
                assert_never(occurrence)
    return tuple(reports)


def _occurrence_of(failure: workspace.LoadFailure) -> EngineCondition | UnlistableRoot:
    """The engine condition a load failure is, or `UnlistableRoot` for the one the command stops the run for.

    Args:
        failure: A load failure the model listed.
    """
    condition = failure.condition
    match condition:
        case workspace.UnreadableStructureFile(refusal=refusal):
            return unreadable_path.UnreadablePath(
                failed_at=failure.path, cause=Refused(operation=RefusedOperation.READ, refusal=refusal)
            )
        case workspace.UnrecordedStructureFile():
            return unreadable_path.UnreadablePath(failed_at=failure.path, cause=NotARegularFile())
        case workspace.NonUtf8StructureFile(failure=utf8_failure):
            # The same condition as any file that does not decode, so it is reported as one, at the structure file.
            return invalid_utf8.InvalidUtf8(failure=utf8_failure)
        case workspace.UndecodableStructureSpec(problems=problems):
            return malformed_structure_file.MalformedStructureFile(
                cause=malformed_structure_file.FormatViolated(problems=tuple(str(problem) for problem in problems))
            )
        case workspace.EmptyStructureSpec():
            return malformed_structure_file.MalformedStructureFile(cause=malformed_structure_file.NoRuleStated())
        case workspace.RepeatedOutlineSections(sections=sections):
            return unusable_structure_file.UnusableStructureFile(
                cause=unusable_structure_file.RepeatedOutlineSection(sections=sections)
            )
        case workspace.RepeatedForbiddenSections(sections=sections):
            return unusable_structure_file.UnusableStructureFile(
                cause=unusable_structure_file.RepeatedForbiddenSection(sections=sections)
            )
        case workspace.ForbiddenOutlineSections(sections=sections):
            return unusable_structure_file.UnusableStructureFile(
                cause=unusable_structure_file.ForbiddenOutlineSection(sections=sections)
            )
        case workspace.AdjacentAnyRuns():
            return unusable_structure_file.UnusableStructureFile(cause=unusable_structure_file.AdjacentAnyRuns())
        case workspace.InvalidTitlePattern(pattern=pattern, problem=problem):
            return unusable_structure_file.UnusableStructureFile(
                cause=unusable_structure_file.InvalidTitlePattern(pattern=pattern, problem=problem)
            )
        case workspace.InvalidFrontmatterSchema(problem=problem):
            return unusable_structure_file.UnusableStructureFile(
                cause=unusable_structure_file.InvalidFrontmatterSchema(problem=problem)
            )
        case workspace.IdentifiedFrontmatterSchema():
            return unusable_structure_file.UnusableStructureFile(
                cause=unusable_structure_file.IdentifiedFrontmatterSchema()
            )
        case workspace.ForeignFrontmatterDialect(dialect=dialect):
            return unusable_structure_file.UnusableStructureFile(
                cause=unusable_structure_file.ForeignFrontmatterDialect(dialect=repr(dialect))
            )
        case workspace.UnresolvableFrontmatterSchemaRef(ref=ref):
            return unusable_structure_file.UnusableStructureFile(
                cause=unusable_structure_file.UnresolvableFrontmatterSchemaRef(ref=repr(ref))
            )
        case workspace.CyclicFrontmatterSchemaRef(ref=ref):
            return unusable_structure_file.UnusableStructureFile(
                cause=unusable_structure_file.CyclicFrontmatterSchemaRef(ref=repr(ref))
            )
        case workspace.UntypedFrontmatterSchema():
            return unusable_structure_file.UnusableStructureFile(
                cause=unusable_structure_file.UntypedFrontmatterSchema()
            )
        case workspace.UnlistableDirectory():
            return UnlistableRoot(failure)
        case workspace.UnlistableCorpusDirectory(refusal=refusal):
            return unreadable_path.UnreadablePath(
                failed_at=failure.path, cause=Refused(operation=RefusedOperation.LIST, refusal=refusal)
            )
        case workspace.UnresolvableSkillsDirectory(refusal=refusal):
            return unreadable_path.UnreadablePath(
                failed_at=failure.path, cause=Refused(operation=RefusedOperation.RESOLVE, refusal=refusal)
            )
        case workspace.UninspectableSkillsDirectory(failed_at=failed_at, refusal=refusal):
            return unreadable_path.UnreadablePath(
                failed_at=failed_at, cause=Refused(operation=RefusedOperation.INSPECT, refusal=refusal)
            )
        case workspace.UnlistableSkillsDirectory(failed_at=failed_at, refusal=refusal):
            return unreadable_path.UnreadablePath(
                failed_at=failed_at, cause=Refused(operation=RefusedOperation.LIST, refusal=refusal)
            )
        case workspace.UnresolvableSkillEntry(refusal=refusal):
            return unreadable_path.UnreadablePath(
                failed_at=failure.path, cause=Refused(operation=RefusedOperation.RESOLVE, refusal=refusal)
            )
        case workspace.UninspectableSkillEntry(failed_at=failed_at, refusal=refusal):
            return unreadable_path.UnreadablePath(
                failed_at=failed_at, cause=Refused(operation=RefusedOperation.INSPECT, refusal=refusal)
            )
        case workspace.UnlistableSkillDirectory(failed_at=failed_at, refusal=refusal):
            return unreadable_path.UnreadablePath(
                failed_at=failed_at, cause=Refused(operation=RefusedOperation.LIST, refusal=refusal)
            )
        case workspace.UnresolvableSkillFile(failed_at=failed_at, refusal=refusal):
            return unreadable_path.UnreadablePath(
                failed_at=failed_at, cause=Refused(operation=RefusedOperation.RESOLVE, refusal=refusal)
            )
        case workspace.UninspectableSkillFile(failed_at=failed_at, refusal=refusal):
            return unreadable_path.UnreadablePath(
                failed_at=failed_at, cause=Refused(operation=RefusedOperation.INSPECT, refusal=refusal)
            )
        case _:
            assert_never(condition)
