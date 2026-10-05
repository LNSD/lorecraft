"""The rules engine's runner: every enabled rule over each subject, through one rule table.

The runner never names a rule. A rule joins its input's partition of the table through the registry, and the
runner runs every rule of a partition over the input built for it, so adding a rule never edits this module.
What it names is each input kind, in one hand-written branch, so `rule.check(input)` stays typed; adding an input
adds a branch here.

A subject's status comes before any rule. Each subject is decoded once: one that does not decode is reported as
`UndecodableSubject`, whatever the table enables, and no rule sees it. For each input kind an enabled rule reads,
the input is built once from the queries, and a subject no specification governs for it records that input kind
as ungoverned rather than a diagnostic. An input no enabled rule reads is never built, so its queries are never
asked.

The subjects are documents and skills, each matched to its own function, so a subject kind without one is a type
error. A document is handed over as its ref, and a skill as the `SkillLocation` the model hands out for it, since a
rule over a skill may read where its directory leads. A skill is its `SKILL.md`, decoded and reported at that path,
under its ref; its resources are not subjects yet. The command
line does not run this yet, and the per-check pipelines in `run` serve it until then.
"""

from collections.abc import Iterable
from typing import assert_never

from lorecraft.project.document import DocumentRef
from lorecraft.project.skill import SkillLocation
from lorecraft.rules.inputs import (
    FrontmatterBlockInput,
    HeadingsInput,
    InputKind,
    OutlineDivergenceInput,
    SchemaProblemsInput,
    TokenCountInput,
)
from lorecraft.vfs import ResolvedPath

from .database import Database
from .inputs import (
    Ungoverned,
    build_document_frontmatter_block_input,
    build_document_schema_problems_input,
    build_headings_input,
    build_line_count_input,
    build_outline_divergence_input,
    build_skill_frontmatter_block_input,
    build_skill_schema_problems_input,
    build_token_count_input,
)
from .report import CheckedSubject, Diagnostic, RuleDiagnostic, SubjectReport, UndecodableSubject
from .table import RuleTable
from .text import DocumentText, SkillText, Undecodable

# A subject the runner checks: a document, by its ref, or a skill, by the location the model hands out for it. Its
# report holds its ref either way: a `SkillLocation` carries the skill's ref.
type Subject = DocumentRef | SkillLocation


def check_subjects(database: Database, subjects: Iterable[Subject], table: RuleTable) -> tuple[SubjectReport, ...]:
    """Run the table's rules over each document and skill, and report each in the order given.

    Args:
        database: The revision the subjects are read from; its model decides which specifications govern each.
        subjects: The documents and skills to check; a document in no corpus the database's model holds is
            ungoverned for every input a specification governs.
        table: The rules the run enables, each with its severity.

    Raises:
        DocumentReadError: If a document is missing from the snapshot; a decode failure is a diagnostic.
        SkillReadError: If a skill's `SKILL.md` is missing from the snapshot; a decode failure is a diagnostic.
        DirListError: If the model is not loaded yet and the specification directory or docs/ cannot be listed.
        CorpusListError: If the model is not loaded yet and a corpus directory cannot be listed.
        StructureSchemaReadError: If the model is not loaded yet and a structure specification cannot be read.
        StructureSpecDecodeError: If the model is not loaded yet and a structure specification is not JSON in the
            dialect's shape.
        EmptyStructureSpecError: If the model is not loaded yet and a structure specification states no rule.
        RepeatedOutlineSectionError: If the model is not loaded yet and an outline names a section twice.
        RepeatedForbiddenSectionError: If the model is not loaded yet and a specification forbids a section twice.
        ForbiddenOutlineSectionError: If the model is not loaded yet and a specification forbids a section its
            outline names.
        AdjacentAnyRunsError: If the model is not loaded yet and an outline places two `any` runs side by side.
        InvalidFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema is rejected by the
            meta-schema.
        FrontmatterSchemaIdError: If the model is not loaded yet and a schema in a frontmatter schema carries `$id`.
        ForeignFrontmatterDialectError: If the model is not loaded yet and a schema in a frontmatter schema names
            another dialect.
        UntypedFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema's root does not state
            an object.
        DirResolveError: If the model is not loaded yet and a skills directory cannot be resolved.
        EntryInspectError: If the model is not loaded yet and an entry on the way to a skills directory cannot be
            inspected, or a link's target read, while looking for where it leaves the repository.
        SkillsDirListError: If the model is not loaded yet and a skills directory cannot be listed.
        SkillEntryResolveError: If the model is not loaded yet and a symlinked skill entry cannot be resolved.
        SkillDirListError: If the model is not loaded yet and a skill directory cannot be listed.
        SkillFileResolveError: If the model is not loaded yet and a symlinked SKILL.md cannot be resolved.
    """
    reports: list[SubjectReport] = []
    for subject in subjects:
        match subject:
            case DocumentRef():
                reports.append(_check_document(database, subject, table))
            case SkillLocation():
                reports.append(_check_skill(database, subject, table))
            case _:
                assert_never(subject)
    return tuple(reports)


def _check_document(database: Database, ref: DocumentRef, table: RuleTable) -> SubjectReport:
    """Decode one document, then run the table's rules over it if it decoded.

    Args:
        database: The revision the document is read from.
        ref: The document to check.
        table: The rules the run enables.

    Raises:
        DocumentReadError: If the document is missing from the snapshot; a decode failure is a diagnostic.
        DirListError: If the model is not loaded yet and the specification directory or docs/ cannot be listed.
        CorpusListError: If the model is not loaded yet and a corpus directory cannot be listed.
        StructureSchemaReadError: If the model is not loaded yet and a structure specification cannot be read.
        StructureSpecDecodeError: If the model is not loaded yet and a structure specification is not JSON in the
            dialect's shape.
        EmptyStructureSpecError: If the model is not loaded yet and a structure specification states no rule.
        RepeatedOutlineSectionError: If the model is not loaded yet and an outline names a section twice.
        RepeatedForbiddenSectionError: If the model is not loaded yet and a specification forbids a section twice.
        ForbiddenOutlineSectionError: If the model is not loaded yet and a specification forbids a section its
            outline names.
        AdjacentAnyRunsError: If the model is not loaded yet and an outline places two `any` runs side by side.
        InvalidFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema is rejected by the
            meta-schema.
        FrontmatterSchemaIdError: If the model is not loaded yet and a schema in a frontmatter schema carries `$id`.
        ForeignFrontmatterDialectError: If the model is not loaded yet and a schema in a frontmatter schema names
            another dialect.
        UntypedFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema's root does not state
            an object.
        DirResolveError: If the model is not loaded yet and a skills directory cannot be resolved.
        EntryInspectError: If the model is not loaded yet and an entry on the way to a skills directory cannot be
            inspected, or a link's target read, while looking for where it leaves the repository.
        SkillsDirListError: If the model is not loaded yet and a skills directory cannot be listed.
        SkillEntryResolveError: If the model is not loaded yet and a symlinked skill entry cannot be resolved.
        SkillDirListError: If the model is not loaded yet and a skill directory cannot be listed.
        SkillFileResolveError: If the model is not loaded yet and a symlinked SKILL.md cannot be resolved.
    """
    source = database.text(ref)
    match source:
        case Undecodable():
            return UndecodableSubject(ref)
        case DocumentText():
            return _check_document_text(database, source, table)
        case _:
            assert_never(source)


def _check_document_text(database: Database, source: DocumentText, table: RuleTable) -> CheckedSubject:
    """Build each input an enabled rule reads from a decoded document, and run those rules over it.

    Args:
        database: The revision the document is read from.
        source: The document's text, the witness every per-file query takes.
        table: The rules the run enables.

    Raises:
        DirListError: If the model is not loaded yet and the specification directory or docs/ cannot be listed.
        CorpusListError: If the model is not loaded yet and a corpus directory cannot be listed.
        StructureSchemaReadError: If the model is not loaded yet and a structure specification cannot be read.
        StructureSpecDecodeError: If the model is not loaded yet and a structure specification is not JSON in the
            dialect's shape.
        EmptyStructureSpecError: If the model is not loaded yet and a structure specification states no rule.
        RepeatedOutlineSectionError: If the model is not loaded yet and an outline names a section twice.
        RepeatedForbiddenSectionError: If the model is not loaded yet and a specification forbids a section twice.
        ForbiddenOutlineSectionError: If the model is not loaded yet and a specification forbids a section its
            outline names.
        AdjacentAnyRunsError: If the model is not loaded yet and an outline places two `any` runs side by side.
        InvalidFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema is rejected by the
            meta-schema.
        FrontmatterSchemaIdError: If the model is not loaded yet and a schema in a frontmatter schema carries `$id`.
        ForeignFrontmatterDialectError: If the model is not loaded yet and a schema in a frontmatter schema names
            another dialect.
        UntypedFrontmatterSchemaError: If the model is not loaded yet and a frontmatter schema's root does not state
            an object.
        DirResolveError: If the model is not loaded yet and a skills directory cannot be resolved.
        EntryInspectError: If the model is not loaded yet and an entry on the way to a skills directory cannot be
            inspected, or a link's target read, while looking for where it leaves the repository.
        SkillsDirListError: If the model is not loaded yet and a skills directory cannot be listed.
        SkillEntryResolveError: If the model is not loaded yet and a symlinked skill entry cannot be resolved.
        SkillDirListError: If the model is not loaded yet and a skill directory cannot be listed.
        SkillFileResolveError: If the model is not loaded yet and a symlinked SKILL.md cannot be resolved.
    """
    diagnostics: list[Diagnostic] = []
    ungoverned: list[InputKind] = []

    # The frontmatter is never asked for when no enabled rule reads it.
    if table.frontmatter_block_rules:
        frontmatter_block_input = build_document_frontmatter_block_input(database, source)
        match frontmatter_block_input:
            case Ungoverned():
                ungoverned.append(InputKind.FRONTMATTER_BLOCK)
            case FrontmatterBlockInput():
                for enabled in table.frontmatter_block_rules:
                    for occurrence in enabled.rule.check(frontmatter_block_input):
                        diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))
            case _:
                assert_never(frontmatter_block_input)

    # The frontmatter is never held to its schemas when no enabled rule reads what they reject.
    if table.schema_problems_rules:
        schema_problems_input = build_document_schema_problems_input(database, source)
        match schema_problems_input:
            case Ungoverned():
                ungoverned.append(InputKind.SCHEMA_PROBLEMS)
            case SchemaProblemsInput():
                for enabled in table.schema_problems_rules:
                    for occurrence in enabled.rule.check(schema_problems_input):
                        diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))
            case _:
                assert_never(schema_problems_input)

    # The token count is never asked for when no enabled rule reads it.
    if table.token_count_rules:
        token_count_input = build_token_count_input(database, source)
        match token_count_input:
            case Ungoverned():
                ungoverned.append(InputKind.TOKEN_COUNT)
            case TokenCountInput():
                for enabled in table.token_count_rules:
                    for occurrence in enabled.rule.check(token_count_input):
                        diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))
            case _:
                assert_never(token_count_input)

    # The document is never parsed when no enabled rule reads its headings.
    if table.headings_rules:
        headings_input = build_headings_input(database, source)
        match headings_input:
            case Ungoverned():
                ungoverned.append(InputKind.HEADINGS)
            case HeadingsInput():
                for enabled in table.headings_rules:
                    for occurrence in enabled.rule.check(headings_input):
                        diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))
            case _:
                assert_never(headings_input)

    # The document is never matched against its outlines when no enabled rule reads where it diverges.
    if table.outline_divergence_rules:
        outline_divergence_input = build_outline_divergence_input(database, source)
        match outline_divergence_input:
            case Ungoverned():
                ungoverned.append(InputKind.OUTLINE_DIVERGENCE)
            case OutlineDivergenceInput():
                for enabled in table.outline_divergence_rules:
                    for occurrence in enabled.rule.check(outline_divergence_input):
                        diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))
            case _:
                assert_never(outline_divergence_input)

    return CheckedSubject(source.ref, diagnostics=tuple(diagnostics), ungoverned=tuple(ungoverned))


def _check_skill(database: Database, location: SkillLocation, table: RuleTable) -> SubjectReport:
    """Decode one skill's `SKILL.md`, then run the table's rules over it if it decoded.

    Args:
        database: The revision the skill is read from.
        location: The skill to check, and where its files live, as the model hands it out.
        table: The rules the run enables.

    Raises:
        SkillReadError: If the skill's `SKILL.md` is missing from the snapshot; a decode failure is a diagnostic.
    """
    ref = location.ref
    source = database.skill_text(ref)
    match source:
        case Undecodable():
            return UndecodableSubject(ref)
        case SkillText():
            return _check_skill_text(database, source, _link_target(location), table)
        case _:
            assert_never(source)


def _check_skill_text(
    database: Database, source: SkillText, link_target: ResolvedPath | None, table: RuleTable
) -> CheckedSubject:
    """Build each input an enabled rule reads from a decoded `SKILL.md`, and run those rules over it. Raises nothing.

    Args:
        database: The revision the skill is read from.
        link_target: The resolved directory the skill's listed directory leads to when it is a link, or `None` when
            it is not.
        source: The skill's `SKILL.md` text, the witness every per-file query takes.
        table: The rules the run enables.
    """
    diagnostics: list[Diagnostic] = []

    # The frontmatter is never asked for when no enabled rule reads it.
    if table.frontmatter_block_rules:
        frontmatter_block_input = build_skill_frontmatter_block_input(database, source, link_target)
        for enabled in table.frontmatter_block_rules:
            for occurrence in enabled.rule.check(frontmatter_block_input):
                diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))

    # The frontmatter is never held to the Agent Skills specification when no enabled rule reads what it rejects.
    if table.schema_problems_rules:
        schema_problems_input = build_skill_schema_problems_input(database, source)
        for enabled in table.schema_problems_rules:
            for occurrence in enabled.rule.check(schema_problems_input):
                diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))

    # The line count is never asked for when no enabled rule reads it.
    if table.line_count_rules:
        line_count_input = build_line_count_input(database, source)
        for enabled in table.line_count_rules:
            for occurrence in enabled.rule.check(line_count_input):
                diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))

    # The package governs every input a skill has, so none is ever ungoverned.
    return CheckedSubject(source.ref, diagnostics=tuple(diagnostics), ungoverned=())


def _link_target(location: SkillLocation) -> ResolvedPath | None:
    """The resolved directory a skill's listed directory leads to when it is a link, or `None` when it is not.

    Read from the location the model hands out, never from the disk. Raises nothing.

    Args:
        location: The skill, and where its files live.
    """
    if location.resolves_to == location.ref.directory:
        return None
    return location.resolves_to
