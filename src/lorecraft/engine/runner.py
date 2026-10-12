"""The rules engine's shared runner: every enabled rule over a subject, through one rule table.

This is what every mode of the engine shares: decoding a skill and a resource, the governance lookup, facet gating,
and running the table's rules over a subject's context into its report. It holds no mode's policy. A document is
decoded by each mode's own entry point beside this module, `skip.check_subjects` for the check run, so that its
policy for a document a failed layer governs comes after decoding; the entry point matches on the subject kind and
calls the functions here.

The runner never names a rule. A rule joins its base's partition of the table through the registry, and the runner
hands every rule of a partition the subject's context, so adding a rule never edits this module. What it names is
each subject kind, in one hand-written branch, so `rule.check(context)` stays typed; a new fact a rule reads is a
method of the context and a query of the database, never a branch here.

A subject's status comes before any rule. Each subject is decoded once: one that does not decode is reported as
`UndecodableSubject`, whatever the table enables, and no rule sees it. A decoded document is then judged facet by
facet: for each facet an enabled rule over a document or over the frontmatter declares, the runner reads whether the
specifications govern the document for it, runs those rules over the document's context if they do, and records the
facet as ungoverned rather than a diagnostic if they do not. A rule over a Markdown file judges a document under
`Facet.STRUCTURE`, beside the rules over a document that declare it. A document in no corpus, or in one that states no
structure specification, is governed for no facet, and no context is built for it. The package governs every skill and
every resource, so neither is ever ungoverned, and the rules over the frontmatter, over a skill and over a Markdown
file run over its context. A rule over a skill's file judges every `SKILL.md` and every resource, and never a
document. A context asks the database only for what a rule reads, so a fact no enabled rule reads is never computed.

The subjects are documents, skills, skills' resources and layout entries, each matched to its own function, so a
subject kind without one is a type error. A document is handed over as its ref, and a skill as the `SkillLocation` the
model hands out for it, since a rule over a skill may read where its directory leads. A skill is its `SKILL.md`,
decoded and reported at that path, under its ref. A resource is a subject of its own, handed over as the
`SkillResourceLocation` its skill's resource listing gives, since only that listing locates its file: it is decoded at
the file it leads to, and reported under its ref, at the path an agent reaches it by. The runner never lists a skill's
resources itself, so a skill handed over judges its `SKILL.md` alone.

A layout entry is one symlink of the skill layout whose chain leaves the repository, handed over as the
`OutsideSymlink` record the model or a skill's resource listing holds for it. Whether a chain leaves the repository is
decided there, from the link targets the scan recorded; a symlink that stays inside, or dangles inside, is no layout
entry. The caller collects the entries its selection covers as it chooses every other subject, from two queries: the
model's `outside_symlinks`, for a skills directory, an entry in one or an entry's `SKILL.md`, and the
`skill_resources` listing of each skill it checks whole, for a symlink inside that skill. Each is reported at the path
an agent reaches it by, in the order given like every subject. A symlink has no text, so it is never decoded, and the
package governs the skill layout, so it is never ungoverned: every rule over a layout entry judges it through its
context.
"""

from typing import assert_never

from lorecraft.project.database import (
    Database,
    DatabaseDocumentContext,
    DatabaseLayoutContext,
    DatabaseSkillContext,
    DatabaseSkillResourceContext,
    DocumentText,
    SkillResourceText,
    SkillText,
    Undecodable,
)
from lorecraft.project.document import DocumentRef
from lorecraft.project.skill import OutsideSymlink, SkillLocation, SkillResourceLocation
from lorecraft.project.workspace import Governance
from lorecraft.rules.report import (
    CheckedLayoutEntry,
    CheckedSubject,
    Diagnostic,
    RuleDiagnostic,
    SubjectReport,
    UndecodableSubject,
)
from lorecraft.rules.subject import Facet, MarkdownRule
from lorecraft.rules.table import EnabledRule, RuleTable

# A subject an entry point checks: a document, by its ref, a skill, by the location the model hands out for it, a
# skill's resource, by the location its skill's resource listing gives, or a layout entry, by the record of a symlink
# whose chain leaves the repository. A document's, a skill's and a resource's report holds its ref, which each
# location carries; a layout entry's holds the path an agent reaches the symlink by.
type Subject = DocumentRef | SkillLocation | SkillResourceLocation | OutsideSymlink


def judge_document(database: Database, source: DocumentText, table: RuleTable) -> CheckedSubject:
    """Run the enabled rules over a decoded document, each over what the specifications govern it for.

    A mode decodes the document and decides what a layer that failed to load means for it; this judges it by the
    specifications that govern it.

    Args:
        database: The revision the document is read from.
        source: The document's text, the witness every per-file query takes.
        table: The rules the run enables.
    """
    diagnostics: list[Diagnostic] = []
    ungoverned: list[Facet] = []

    # Each rule over the document or its frontmatter reads it through its context, and only when the specifications
    # govern the facet it reads; a rule over a Markdown file reads it under `Facet.STRUCTURE`, as its base states.
    # Governance is never read when no rule over a document, over the frontmatter or over a Markdown file is enabled.
    # The ungoverned facets are recorded in the order the runner reaches them.
    if table.frontmatter_rules or table.document_rules or table.markdown_rules:
        context = _find_document_context(database, source)
        for facet in Facet:
            frontmatter_rules = table.frontmatter_rules_governed_by(facet)
            facet_rules = table.document_rules_governed_by(facet)
            # The rules over a Markdown file join the rules over a document that declare the structure facet.
            markdown_rules: tuple[EnabledRule[MarkdownRule], ...] = ()
            if facet is Facet.STRUCTURE:
                markdown_rules = table.markdown_rules
            # A facet no enabled rule reads is never looked at, so it is never reported as ungoverned either.
            if not frontmatter_rules and not facet_rules and not markdown_rules:
                continue
            if context is None or not _is_governed_for(context.specifications(), facet):
                ungoverned.append(facet)
                continue
            for enabled in frontmatter_rules:
                for occurrence in enabled.rule.check(context):
                    diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))
            for enabled in facet_rules:
                for occurrence in enabled.rule.check(context):
                    diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))
            for enabled in markdown_rules:
                for occurrence in enabled.rule.check(context):
                    diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))

    return CheckedSubject(source.ref, diagnostics=tuple(diagnostics), ungoverned=tuple(ungoverned))


def check_skill(database: Database, location: SkillLocation, table: RuleTable) -> SubjectReport:
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
            return UndecodableSubject(ref, source.failure)
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

    # The package governs every skill, so each rule over the frontmatter and each rule over a skill judges it through
    # its context, the frontmatter rules first, as on a document.
    for enabled in table.frontmatter_rules:
        for occurrence in enabled.rule.check(context):
            diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))
    for enabled in table.skill_rules:
        for occurrence in enabled.rule.check(context):
            diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))

    # A skill's Markdown file is its `SKILL.md`, so each rule over a Markdown file judges it through the same context.
    for enabled in table.markdown_rules:
        for occurrence in enabled.rule.check(context):
            diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))

    # The `SKILL.md` is one of the skill's files, so each rule over a skill's file judges it too.
    for enabled in table.skill_file_rules:
        for occurrence in enabled.rule.check(context):
            diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))

    # The package governs a skill for every facet, so it is never ungoverned.
    return CheckedSubject(source.ref, diagnostics=tuple(diagnostics), ungoverned=())


def check_skill_resource(database: Database, location: SkillResourceLocation, table: RuleTable) -> SubjectReport:
    """Decode one resource of a skill, then run the table's rules over it if it decoded.

    Args:
        database: The revision the resource is read from.
        location: The resource to check, and the file it leads to, as its skill's resource listing gives it.
        table: The rules the run enables.

    Raises:
        SkillResourceReadError: If the resource is missing from the snapshot; a decode failure is a diagnostic.
    """
    source = database.skill_resource_text(location)
    match source:
        case Undecodable():
            return UndecodableSubject(location.ref, source.failure)
        case SkillResourceText():
            return _check_skill_resource_text(database, source, table)
        case _:
            assert_never(source)


def _check_skill_resource_text(database: Database, source: SkillResourceText, table: RuleTable) -> CheckedSubject:
    """Run the enabled rules over a decoded resource of a skill. Raises nothing.

    Only a rule over a Markdown file or over a skill's file judges a resource: no rule over a document, over a skill or
    over the frontmatter reads one.

    Args:
        database: The revision the resource is read from.
        source: The resource's text, the witness every per-file query takes.
        table: The rules the run enables.
    """
    diagnostics: list[Diagnostic] = []

    # Building the context asks nothing of the database; each rule asks it only for what it reads.
    context = DatabaseSkillResourceContext(database, source)
    for enabled in table.markdown_rules:
        for occurrence in enabled.rule.check(context):
            diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))
    for enabled in table.skill_file_rules:
        for occurrence in enabled.rule.check(context):
            diagnostics.append(RuleDiagnostic(source.ref.path, occurrence, enabled.severity))

    # The package governs every resource, after the Agent Skills specification, so it is never ungoverned.
    return CheckedSubject(source.ref, diagnostics=tuple(diagnostics), ungoverned=())


def check_layout_entry(outside: OutsideSymlink, table: RuleTable) -> CheckedLayoutEntry:
    """Run the enabled rules over one symlink of the skill layout whose chain leaves the repository. Raises nothing.

    Args:
        outside: The symlink, as the model or a skill's resource listing records it.
        table: The rules the run enables.
    """
    diagnostics: list[Diagnostic] = []

    # The symlink has no text to decode, and the package governs the skill layout, so each rule over a layout entry
    # judges it through its context, which reads the record and asks the database nothing.
    context = DatabaseLayoutContext(outside)
    for enabled in table.layout_rules:
        for occurrence in enabled.rule.check(context):
            diagnostics.append(RuleDiagnostic(outside.path, occurrence, enabled.severity))

    return CheckedLayoutEntry(outside.path, diagnostics=tuple(diagnostics))


def _find_document_context(database: Database, source: DocumentText) -> DatabaseDocumentContext | None:
    """The context of a decoded document, or `None` when no facet can govern it.

    No facet governs a document in no corpus the database's model holds, nor one whose corpus has no structure
    specification that loaded: without the corpus's, a namespace's governs nothing, as `structure_specs` states.
    Both are read from `Database.governance`, so the specifications are looked up once for the document, not once
    per reader.

    Args:
        database: The revision the document is read from; its model decides which specifications govern it.
        source: The document's text, the witness every per-file query takes.
    """
    governance = database.governance(source.ref)
    if governance is None:
        return None
    if governance.corpus_structure() is None:
        return None
    return DatabaseDocumentContext(database, source)


def _is_governed_for(governance: Governance, facet: Facet) -> bool:
    """Whether the specifications that govern a document govern it for a facet. Raises nothing.

    Args:
        governance: The specifications that govern the document, as `Database.governance` returns them.
        facet: The facet a rule over the document declares.
    """
    match facet:
        case Facet.FRONTMATTER:
            return bool(governance.frontmatter_schemas())
        case Facet.STRUCTURE:
            return governance.corpus_structure() is not None
        case Facet.OUTLINE:
            return any(structure_spec.outline for structure_spec in governance.structure_specs())
        case Facet.BUDGET:
            return any(structure_spec.tokens is not None for structure_spec in governance.structure_specs())
        case _:
            assert_never(facet)
