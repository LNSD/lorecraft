"""The rules engine's shared runner: every enabled rule over a subject, through one rule table.

This is what every mode of the engine shares: decoding a resource, the governance lookup, facet gating, and running
the table's rules over a subject's context into its report. It holds no mode's policy. A document and a skill entry
are decoded by each mode's own entry point beside this module, `skip.check_subjects` for the check run, so that its
policy for an item a failed layer governs comes after decoding; the entry point hands the decoded item to
`judge_item` and the other subjects to the functions here.

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

The subjects are documents, skills, skills' resources and layout entries. A decoded document or skill entry is
judged by the one entry `judge_item`; a resource and a layout entry each have a function of their own, so a subject
kind without one is a type error. A document is handed over as its ref, and a skill as the `SkillLocation` the
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

from collections.abc import Callable
from dataclasses import dataclass
from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import (
    Database,
    DatabaseItemContext,
    DatabaseLayoutContext,
    DatabaseSkillResourceContext,
    DocumentText,
    SkillResourceText,
    SkillText,
    Undecodable,
)
from lorecraft.project.database import ItemText as DecodedItem
from lorecraft.project.document import DocumentRef
from lorecraft.project.item import MarkdownItemRef
from lorecraft.project.skill import OutsideSymlink, SkillAliasRef, SkillLocation, SkillResourceLocation
from lorecraft.project.workspace import Governance
from lorecraft.rules.declaration import Rule
from lorecraft.rules.report import (
    CheckedDocument,
    CheckedLayoutEntry,
    CheckedSkillFile,
    Diagnostic,
    RuleDiagnostic,
    SubjectReport,
    UndecodableSubject,
)
from lorecraft.rules.subject import Facet
from lorecraft.rules.table import EnabledRule, RuleTable


# A subject an entry point checks: a document, a skill, a resource, a refused skill alias, or a layout entry. Each
# report holds its ref or the path an agent reaches the symlink by.
@dataclass(frozen=True, slots=True)
class RefusedSkillSubject:
    """A skill alias whose resource listing reached a refused docs path.

    Attributes:
        ref: The symlink path where an agent reaches the refused alias, including a directory alias.
        refused_at: The docs path the skill listing could not inspect.
    """

    ref: SkillAliasRef
    refused_at: RootRelativePath


type Subject = DocumentRef | SkillLocation | SkillResourceLocation | OutsideSymlink | RefusedSkillSubject


type ItemText = DocumentText | SkillText
"""A decoded document or skill entry: the witness the entry point hands the runner after its own policy."""


def judge_item(database: Database, source: ItemText, table: RuleTable) -> CheckedDocument | CheckedSkillFile:
    """Run the enabled rules over a decoded document or skill entry, each over what the specifications govern it for.

    A mode decodes the item and decides what a layer that failed to load means for it; this judges it by the
    specifications that govern it. The rules over the frontmatter and over a Markdown file run the same way over both
    kinds, through the context of the kind.

    Args:
        database: The revision the item is read from.
        source: The item's text, the witness every per-file query takes.
        table: The rules the run enables.
    """
    match source:
        case DocumentText():
            return _judge_document(database, source, table)
        case SkillText():
            return _judge_skill(database, source, table)
        case _:
            assert_never(source)


def _witness(database: Database, path: RootRelativePath) -> DecodedItem:
    """The decoded text of an item whose compatibility witness exists, so its file decodes.

    Args:
        database: The revision the item is read from.
        path: Where the item is reported.
    """
    item = database.item_text(MarkdownItemRef(path))
    if isinstance(item, Undecodable):
        raise AssertionError(f'{path} has a witness, so it decodes')
    return item


def _located[R: Rule](
    path: RootRelativePath, partition: tuple[EnabledRule[R], ...], check: Callable[[type[R]], tuple[R, ...]]
) -> list[Diagnostic]:
    """Every occurrence of the partition's rules, each located at the path at its rule's severity, in code order.

    Args:
        path: Where the subject is reported.
        partition: The enabled rules of one base.
        check: Runs one rule of the partition over the subject's context.
    """
    return [
        RuleDiagnostic(path, occurrence, enabled.severity)
        for enabled in partition
        for occurrence in check(enabled.rule)
    ]


def _judge_document(database: Database, source: DocumentText, table: RuleTable) -> CheckedDocument:
    """Run the enabled rules over a decoded document, each over what the specifications govern it for.

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
        governance = database.governance(source.ref)
        governed = governance is not None and governance.corpus_structure() is not None
        context = DatabaseItemContext(database, _witness(database, source.ref.path)) if governed else None
        for facet in Facet:
            # The rules over a Markdown file join the rules over a document that declare the structure facet.
            markdown_rules = table.markdown_rules if facet is Facet.STRUCTURE else ()
            frontmatter_rules = table.frontmatter_rules_governed_by(facet)
            facet_rules = table.document_rules_governed_by(facet)
            # A facet no enabled rule reads is never looked at, so it is never reported as ungoverned either.
            if not frontmatter_rules and not facet_rules and not markdown_rules:
                continue
            if context is None or not _is_governed_for(context.specifications(), facet):
                ungoverned.append(facet)
                continue
            path = source.ref.path
            diagnostics.extend(_located(path, frontmatter_rules, lambda rule: rule.check(context)))
            diagnostics.extend(_located(path, facet_rules, lambda rule: rule.check(context)))
            diagnostics.extend(_located(path, markdown_rules, lambda rule: rule.check(context)))

    return CheckedDocument(source.ref, diagnostics=tuple(diagnostics), ungoverned=tuple(ungoverned))


def _judge_skill(database: Database, source: SkillText, table: RuleTable) -> CheckedSkillFile:
    """Run the enabled rules over a decoded `SKILL.md`. Raises nothing.

    The package governs a skill for every facet, so each rule judges it and the report holds no ungoverned facets.
    The frontmatter rules come first, as on a document; a skill's Markdown file is its `SKILL.md`, and it is one of the
    skill's files, so each rule over either judges it through the same context.

    Args:
        database: The revision the skill is read from.
        source: The skill's `SKILL.md` text, the witness every per-file query takes.
        table: The rules the run enables.
    """
    # Building the context asks nothing of the database; each rule asks it only for what it reads.
    context = DatabaseItemContext(database, _witness(database, source.ref.path))
    path = source.ref.path
    diagnostics = [
        *_located(path, table.frontmatter_rules, lambda rule: rule.check(context)),
        *_located(path, table.skill_rules, lambda rule: rule.check(context)),
        *_located(path, table.markdown_rules, lambda rule: rule.check(context)),
        *_located(path, table.skill_file_rules, lambda rule: rule.check(context)),
    ]
    return CheckedSkillFile(source.ref, diagnostics=tuple(diagnostics))


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


def _check_skill_resource_text(database: Database, source: SkillResourceText, table: RuleTable) -> CheckedSkillFile:
    """Run the enabled rules over a decoded resource of a skill. Raises nothing.

    Only a rule over a Markdown file or over a skill's file judges a resource: no rule over a document, over a skill or
    over the frontmatter reads one.

    Args:
        database: The revision the resource is read from.
        source: The resource's text, the witness every per-file query takes.
        table: The rules the run enables.
    """
    # Building the context asks nothing of the database; each rule asks it only for what it reads.
    context = DatabaseSkillResourceContext(database, source)
    path = source.ref.path
    diagnostics = [
        *_located(path, table.markdown_rules, lambda rule: rule.check(context)),
        *_located(path, table.skill_file_rules, lambda rule: rule.check(context)),
    ]

    # The package governs every resource, after the Agent Skills specification, so the report holds no ungoverned facet.
    return CheckedSkillFile(source.ref, diagnostics=tuple(diagnostics))


def check_layout_entry(outside: OutsideSymlink, table: RuleTable) -> CheckedLayoutEntry:
    """Run the enabled rules over one symlink of the skill layout whose chain leaves the repository. Raises nothing.

    Args:
        outside: The symlink, as the model or a skill's resource listing records it.
        table: The rules the run enables.
    """
    # The symlink has no text to decode, and the package governs the skill layout, so each rule over a layout entry
    # judges it through its context, which reads the record and asks the database nothing.
    context = DatabaseLayoutContext(outside)
    diagnostics = _located(outside.path, table.layout_rules, lambda rule: rule.check(context))

    return CheckedLayoutEntry(outside.path, diagnostics=tuple(diagnostics))


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
