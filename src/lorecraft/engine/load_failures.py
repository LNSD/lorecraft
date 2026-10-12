"""What a run reports for the units of the declaration that failed to load: one report per failure, at its own path.

The model records each failure as plain facts and decides no policy (adr-015). This is where a failure becomes
what a run reports: the engine condition of its own code, in a `LoadFailureReport` filed at the failure's path, so a
failure is reported once, at its origin, whatever it touches and whatever the configuration and the selection.

A condition and the record that stands for it are declared apart, in `lorecraft.rules.engine` and in
`lorecraft.project.workspace`, and often share a name; the records are read as `workspace.<Record>` and each condition
as `<module>.<Condition>`, so the two are never confused.
"""

from typing import assert_never

from lorecraft.project import workspace
from lorecraft.rules.declaration import EngineCondition
from lorecraft.rules.engine import (
    adjacent_any_runs,
    empty_structure_file,
    forbidden_outline_section,
    foreign_frontmatter_dialect,
    frontmatter_schema_id,
    invalid_frontmatter_schema,
    invalid_title_pattern,
    invalid_utf8,
    malformed_structure_file,
    repeated_forbidden_section,
    repeated_outline_section,
    unlistable_corpus_directory,
    unreadable_skill_entry,
    unreadable_skill_file,
    unreadable_skills_directory,
    unreadable_structure_file,
    untyped_frontmatter_schema,
)
from lorecraft.rules.engine.__ruleset__ import RefusedOperation
from lorecraft.rules.report import LoadFailureReport


def report_load_failures(model: workspace.WorkspaceModel) -> tuple[LoadFailureReport, ...]:
    """One report per load failure the model lists, each filed at the failure's path; the model lists each once.

    A `docs/` or `docs/__meta__/` that cannot be listed has no report: the command reads it before it selects any
    subject, and stops, since with no corpus and no meta spec known a report over what remained would read as a
    clean result for a workspace that was never checked.

    Args:
        model: The workspace model of the revision; its failures are plain data, so nothing here reads the disk.
    """
    reports: list[LoadFailureReport] = []
    for failure in model.load_failures:
        occurrence = _find_occurrence(failure)
        if occurrence is not None:
            reports.append(LoadFailureReport(failure.path, occurrence))
    return tuple(reports)


def _find_occurrence(failure: workspace.LoadFailure) -> EngineCondition | None:
    """The engine condition a load failure is, or `None` for the one the command stops the run for.

    Args:
        failure: A load failure the model listed.
    """
    condition = failure.condition
    match condition:
        case workspace.UnreadableStructureFile(refusal=refusal):
            return unreadable_structure_file.UnreadableStructureFile(refusal=refusal)
        case workspace.UnrecordedStructureFile():
            return unreadable_structure_file.UnreadableStructureFile(refusal=None)
        case workspace.NonUtf8StructureFile(failure=utf8_failure):
            # The same condition as any file that does not decode, so it is reported as one, at the structure file.
            return invalid_utf8.InvalidUtf8(failure=utf8_failure)
        case workspace.UndecodableStructureSpec(problems=problems):
            return malformed_structure_file.MalformedStructureFile(problems=problems)
        case workspace.EmptyStructureSpec():
            return empty_structure_file.EmptyStructureFile()
        case workspace.RepeatedOutlineSections(sections=sections):
            return repeated_outline_section.RepeatedOutlineSection(sections=sections)
        case workspace.RepeatedForbiddenSections(sections=sections):
            return repeated_forbidden_section.RepeatedForbiddenSection(sections=sections)
        case workspace.ForbiddenOutlineSections(sections=sections):
            return forbidden_outline_section.ForbiddenOutlineSection(sections=sections)
        case workspace.AdjacentAnyRuns():
            return adjacent_any_runs.AdjacentAnyRuns()
        case workspace.InvalidTitlePattern(pattern=pattern, problem=problem):
            return invalid_title_pattern.InvalidTitlePattern(pattern=pattern, problem=problem)
        case workspace.InvalidFrontmatterSchema(problem=problem):
            return invalid_frontmatter_schema.InvalidFrontmatterSchema(problem=problem)
        case workspace.FrontmatterSchemaId():
            return frontmatter_schema_id.FrontmatterSchemaId()
        case workspace.ForeignFrontmatterDialect(dialect=dialect):
            return foreign_frontmatter_dialect.ForeignFrontmatterDialect(dialect=dialect)
        case workspace.UntypedFrontmatterSchema():
            return untyped_frontmatter_schema.UntypedFrontmatterSchema()
        case workspace.UnlistableDirectory():
            return None
        case workspace.UnlistableCorpusDirectory(corpus=corpus, refusal=refusal):
            return unlistable_corpus_directory.UnlistableCorpusDirectory(corpus=corpus, refusal=refusal)
        case workspace.UnresolvableSkillsDirectory(refusal=refusal):
            return unreadable_skills_directory.UnreadableSkillsDirectory(
                operation=RefusedOperation.RESOLVE, failed_at=failure.path, refusal=refusal
            )
        case workspace.UninspectableSkillsDirectory(failed_at=failed_at, refusal=refusal):
            return unreadable_skills_directory.UnreadableSkillsDirectory(
                operation=RefusedOperation.INSPECT, failed_at=failed_at, refusal=refusal
            )
        case workspace.UnlistableSkillsDirectory(failed_at=failed_at, refusal=refusal):
            return unreadable_skills_directory.UnreadableSkillsDirectory(
                operation=RefusedOperation.LIST, failed_at=failed_at, refusal=refusal
            )
        case workspace.UnresolvableSkillEntry(refusal=refusal):
            return unreadable_skill_entry.UnreadableSkillEntry(
                operation=RefusedOperation.RESOLVE, failed_at=failure.path, refusal=refusal
            )
        case workspace.UninspectableSkillEntry(failed_at=failed_at, refusal=refusal):
            return unreadable_skill_entry.UnreadableSkillEntry(
                operation=RefusedOperation.INSPECT, failed_at=failed_at, refusal=refusal
            )
        case workspace.UnlistableSkillDirectory(failed_at=failed_at, refusal=refusal):
            return unreadable_skill_entry.UnreadableSkillEntry(
                operation=RefusedOperation.LIST, failed_at=failed_at, refusal=refusal
            )
        case workspace.UnresolvableSkillFile(failed_at=failed_at, refusal=refusal):
            return unreadable_skill_file.UnreadableSkillFile(
                operation=RefusedOperation.RESOLVE, failed_at=failed_at, refusal=refusal
            )
        case workspace.UninspectableSkillFile(failed_at=failed_at, refusal=refusal):
            return unreadable_skill_file.UnreadableSkillFile(
                operation=RefusedOperation.INSPECT, failed_at=failed_at, refusal=refusal
            )
        case _:
            assert_never(condition)
