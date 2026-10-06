"""The rules engine's runner: every enabled rule over each subject, through one rule table.

The runner never names a rule. A rule joins its base's partition of the table through the registry, and the runner
hands every rule of a partition the subject's context, so adding a rule never edits this module. What it names is
each subject kind, in one hand-written branch, so `rule.check(context)` stays typed; a new fact a rule reads is a
method of the context and a query of the database, never a branch here.

A subject's status comes before any rule. Each subject is decoded once: one that does not decode is reported as
`UndecodableSubject`, whatever the table enables, and no rule sees it. A decoded document is then judged facet by
facet: for each facet an enabled rule over a document declares, the runner reads whether the specifications govern
the document for it, runs those rules over the document's context if they do, and records the facet as ungoverned
rather than a diagnostic if they do not. A document in no corpus, or in one that states no structure specification,
is governed for no facet, and no context is built for it. The package governs every skill, so a skill is never
ungoverned. A context asks the database only for what a rule reads, so a fact no enabled rule reads is never
computed.

Every shipped rule still reads an input. For each input kind an enabled rule reads, the input is built once from
the queries, and a subject no specification governs for it records that input kind as ungoverned. Later changes move
those rules onto a context and remove these branches.

The subjects are documents and skills, each matched to its own function, so a subject kind without one is a type
error. A document is handed over as its ref, and a skill as the `SkillLocation` the model hands out for it, since a
rule over a skill may read where its directory leads. A skill is its `SKILL.md`, decoded and reported at that path,
under its ref; its resources are not subjects yet. The command
line does not run this yet, and the per-check pipelines in `run` serve it until then.
"""

from collections.abc import Iterable
from typing import assert_never

from lorecraft.project.database import (
    Database,
    DatabaseDocumentContext,
    DatabaseSkillContext,
    DocumentText,
    SkillText,
    Undecodable,
)
from lorecraft.project.document import DocumentRef
from lorecraft.project.skill import SkillLocation
from lorecraft.project.workspace import Governance
from lorecraft.rules.inputs import (
    FrontmatterBlockInput,
    HeadingsInput,
    InputKind,
    OutlineDivergenceInput,
    SchemaProblemsInput,
    TokenCountInput,
)
from lorecraft.rules.subject import Facet

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
from .report import CheckedSubject, Coverage, Diagnostic, RuleDiagnostic, SubjectReport, UndecodableSubject
from .table import RuleTable

# A subject the runner checks: a document, by its ref, or a skill, by the location the model hands out for it. Its
# report holds its ref either way: a `SkillLocation` carries the skill's ref.
type Subject = DocumentRef | SkillLocation


def check_subjects(database: Database, subjects: Iterable[Subject], table: RuleTable) -> tuple[SubjectReport, ...]:
    """Run the table's rules over each document and skill, and report each in the order given.

    Args:
        database: The revision the subjects are read from; its model decides which specifications govern each.
        subjects: The documents and skills to check; a document in no corpus the database's model holds is
            ungoverned for every facet and input a specification governs.
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
        InvalidTitlePatternError: If the model is not loaded yet and a title's pattern does not compile.
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
        InvalidTitlePatternError: If the model is not loaded yet and a title's pattern does not compile.
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
    """Run the enabled rules over a decoded document, each over what the specifications govern it for.

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
        InvalidTitlePatternError: If the model is not loaded yet and a title's pattern does not compile.
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
    ungoverned: list[Coverage] = []

    # Transitional: every shipped rule still reads an input, built in this function's input branches, which go once
    # those rules read the context.

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

    # Each rule over the document reads it through its context, and only when the specifications govern the facet the
    # rule declares. Governance is never read when no rule over a document is enabled. The loop sits beside the token
    # count's input branch, where that branch goes once its rule reads the context, so the ungoverned facets and input
    # kinds keep their order.
    if table.document_rules:
        context = _find_document_context(database, source)
        for facet in Facet:
            facet_rules = table.document_rules_governed_by(facet)
            # A facet no enabled rule reads is never looked at, so it is never reported as ungoverned either.
            if not facet_rules:
                continue
            if context is None or not _is_governed_for(context.specifications(), facet):
                ungoverned.append(facet)
                continue
            for enabled in facet_rules:
                for occurrence in enabled.rule.check(context):
                    diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))

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
            return _check_skill_text(database, source, location, table)
        case _:
            assert_never(source)


def _check_skill_text(
    database: Database, source: SkillText, location: SkillLocation, table: RuleTable
) -> CheckedSubject:
    """Run the enabled rules over a decoded `SKILL.md`. Raises nothing.

    Args:
        database: The revision the skill is read from.
        source: The skill's `SKILL.md` text, the witness every per-file query takes.
        location: The skill, and where its files live, as the model hands it out.
        table: The rules the run enables.
    """
    diagnostics: list[Diagnostic] = []

    # Building the context asks nothing of the database; each rule asks it only for what it reads.
    context = DatabaseSkillContext(database, source, location)

    # Transitional: every shipped rule still reads an input, built in the branches below, which go once those rules
    # read the context.

    # The frontmatter is never asked for when no enabled rule reads it.
    if table.frontmatter_block_rules:
        frontmatter_block_input = build_skill_frontmatter_block_input(database, source, context.link_target())
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

    # The package governs every skill, so each rule over a skill judges it through its context, after the input
    # branches, as a document's rules run after its own.
    for enabled in table.skill_rules:
        for occurrence in enabled.rule.check(context):
            diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))

    # The package governs a skill for every facet and every input, so it is never ungoverned.
    return CheckedSubject(source.ref, diagnostics=tuple(diagnostics), ungoverned=())


def _find_document_context(database: Database, source: DocumentText) -> DatabaseDocumentContext | None:
    """The context of a decoded document, or `None` when no facet can govern it.

    No facet governs a document in no corpus the database's model holds, nor one whose corpus states no structure
    specification: without the corpus's, a namespace's governs nothing, as `structure_specs` states.

    Args:
        database: The revision the document is read from; its model decides which specifications govern it.
        source: The document's text, the witness every per-file query takes.

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
        InvalidTitlePatternError: If the model is not loaded yet and a title's pattern does not compile.
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
    governance = database.model().find_governance(source.ref)
    if governance is None:
        return None
    corpus_structure = governance.corpus_spec.structure
    if corpus_structure is None:
        return None
    return DatabaseDocumentContext(database, source, governance, corpus_structure)


def _is_governed_for(governance: Governance, facet: Facet) -> bool:
    """Whether the specifications that govern a document govern it for a facet. Raises nothing.

    Args:
        governance: The specifications that govern the document, as the model finds them.
        facet: The facet a rule over the document declares.
    """
    match facet:
        case Facet.FRONTMATTER:
            return bool(governance.frontmatter_schemas())
        case Facet.STRUCTURE:
            return governance.corpus_spec.structure is not None
        case Facet.OUTLINE:
            return any(structure_spec.outline for structure_spec in governance.structure_specs())
        case Facet.BUDGET:
            return any(structure_spec.tokens is not None for structure_spec in governance.structure_specs())
        case _:
            assert_never(facet)
