"""The rules engine's shared runner: every enabled rule over a subject, through one rule table.

This is what every mode of the engine shares: the governance lookup, facet gating, and running
the table's rules over a subject into its report. It holds no mode's policy. A document, specification, skill entry
and resource are decoded by each mode's own entry point beside this module, `skip.check_subjects` for the check run,
so that its policy for an item a failed layer governs comes after decoding; the entry point hands the decoded item to
`judge_item` and the other subjects to the functions here.

The runner never names a rule. A rule joins its base's partition of the table through the registry, and the runner
judges every rule of a partition from its query's facts, so adding a rule never edits this module. What it names is
each subject kind, in one hand-written branch, so the queries stay typed; a new fact a rule reads is a query of the
database, never a branch here.

A subject's status comes before any rule. Each subject is decoded once: one that does not decode is reported as
`UndecodableSubject`, whatever the table enables, and no rule sees it. A decoded document is then judged facet by
facet: for each facet an enabled rule over a document or over the frontmatter declares, the runner reads whether the
specifications govern the document for it, runs those rules over the document if they do, and records the
facet as ungoverned rather than a diagnostic if they do not. A rule over a Markdown file judges a document under
`Facet.STRUCTURE`, beside the rules over a document that declare it. A document in no corpus, or in one that states no
structure specification, is governed for no facet, and no rule is run over it. Package checks judge skill entries
independently of corpus governance. Package Markdown checks judge resources, whose structure and Markdown facets
remain active independently of corpus governance. A rule over a skill's file judges every
`SKILL.md` and every resource, and never a
document. The database answers only for what a rule's query reads, so a fact no enabled rule reads is never computed.

The subjects are those of `skip.Subject`, which defines and dispatches them: documents, specifications, skills,
skills' resources and layout entries. A decoded document, skill entry or resource
is judged by the one entry `judge_item`; a layout entry has a function of its own, so a subject kind without one is a
type error. A document is handed over as its ref, and a skill as the `SkillLocation` the
model hands out for it, since a rule over a skill may read where its directory leads. A skill is its `SKILL.md`,
decoded and reported at that path, under its ref. A resource is a subject of its own, handed over as the
`SkillResourceLocation` its skill's resource listing gives, since only that listing locates its file: it is decoded at
the file it leads to, and reported under its ref, at the path an agent reaches it by, through the same item queries.
The runner never lists a skill's resources itself, so a skill handed over judges its `SKILL.md` alone.

A layout entry is one symlink of the skill layout whose chain leaves the repository, represented by its typed
`SymlinkRef`, or a directory under `docs/` named like a reserved corpus, represented by its typed
`CorpusDirectoryRef`. The caller collects the entries its selection covers as it chooses every other subject, from
queries: the model's `outside_symlinks`, for a skills directory, an entry in one or an entry's `SKILL.md`, its
`sorted_overlapping_directories`, for a reserved-corpus directory, and the `skill_resources` listing of each skill it
checks whole, for a symlink inside that skill. Each is reported at the path an agent reaches it by, in the order given
like every subject. An entry has no text, so it is never decoded, and the package governs the layout, so it is never
ungoverned. The runner judges an entry through `Database.query` by its typed subject ref, so its answer is memoized
just like an item's.
"""

from collections.abc import Callable
from typing import assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import CorpusDirectoryRef, ReservedCorpusDirectory
from lorecraft.project.database import Database, ItemText
from lorecraft.project.item import ItemFacet, ItemKind, MarkdownItemDescriptor, MarkdownItemRef
from lorecraft.project.skill import OutsideSymlink, SymlinkRef
from lorecraft.rules.declaration import Rule
from lorecraft.rules.report import (
    CheckedItem,
    CheckedLayoutEntry,
    Diagnostic,
    RuleDiagnostic,
)
from lorecraft.rules.subject import (
    Facet,
    FrontmatterRule,
    ItemRule,
    QueriedCorpusDirectoryRule,
    QueriedDocumentRule,
    QueriedDocumentSkillRule,
    QueriedFrontmatterRule,
    QueriedMarkdownRule,
    QueriedSkillFileRule,
    QueriedSkillRule,
    QueriedSymlinkRule,
    governing_facet,
)
from lorecraft.rules.table import EnabledRule, RuleTable


def judge_item(database: Database, source: ItemText, table: RuleTable) -> CheckedItem:
    """Run enabled rules over a decoded document, specification, skill entry or resource.

    A mode decodes the item and decides what a layer that failed to load means for it; this judges it by the facets
    its descriptor activates. A rule judges an item of a kind it applies to, and only when the item is governed for the
    facet the rule reads; a facet an applicable enabled rule reads that is not active is recorded as coverage, whatever
    the kind. Nothing here asks where the item came from, so a rule of a new base needs no branch.

    Args:
        database: The revision the item is read from.
        source: The item's text, the witness every per-file query takes.
        table: The rules the run enables.
    """
    descriptor = source.descriptor
    governance = database.item_governance(descriptor.ref)
    failed_skill_layer = (
        descriptor.kind is ItemKind.SKILL_ENTRY and governance is not None and bool(governance.failed_layers())
    )
    builtin_skills_schema = database.model().builtin_skills_schema
    diagnostics: list[Diagnostic] = []
    ungoverned: list[Facet] = []

    # The facets are reached in `Facet` order, then the rules that read none; the ungoverned facets are recorded in
    # that order, and a facet no applicable enabled rule reads is never looked at.
    for facet in (*Facet, None):
        partitions = [
            _reading(partition, descriptor, facet, failed_skill_layer, builtin_skills_schema)
            for partition in (
                table.frontmatter_rules,
                table.document_rules,
                table.markdown_rules,
                table.skill_rules,
                table.skill_file_rules,
            )
        ]
        if not any(partitions):
            continue
        if facet is not None and ItemFacet(facet.value) not in descriptor.active_facets:
            ungoverned.append(facet)
            continue
        for rules in partitions:
            diagnostics.extend(
                _located(descriptor.ref.path, rules, lambda rule: _judged_item(rule, database, descriptor.ref))
            )

    return CheckedItem(descriptor.ref, diagnostics=tuple(diagnostics), ungoverned=tuple(ungoverned))


def _reading[R: ItemRule](
    partition: tuple[EnabledRule[R], ...],
    descriptor: MarkdownItemDescriptor,
    facet: Facet | None,
    failed_skill_layer: bool,
    builtin_skills_schema: bool,
) -> tuple[EnabledRule[R], ...]:
    """The partition's rules that judge an item of the descriptor's kind and read the facet.

    Args:
        partition: The enabled rules of one base.
        descriptor: The item the rules would judge.
        facet: The facet the rules must read, or `None` for those that read none.
        failed_skill_layer: Whether failed skill governance suppresses corpus rules for this entry.
        builtin_skills_schema: Whether built-in Agent Skills frontmatter rules remain active.
    """
    return tuple(
        enabled
        for enabled in partition
        if descriptor.kind in enabled.rule.APPLIES_TO
        and governing_facet(enabled.rule) is facet
        and not (
            descriptor.kind is ItemKind.SKILL_ENTRY
            and not builtin_skills_schema
            and issubclass(enabled.rule, FrontmatterRule)
            and enabled.rule.SKILL_AGENT_SPEC_RULE
        )
        and not (
            descriptor.kind is ItemKind.SKILL_ENTRY
            and issubclass(enabled.rule, QueriedDocumentSkillRule)
            and (not descriptor.governance_corpus or failed_skill_layer)
        )
    )


type ItemQueriedRule[Facts] = (
    QueriedDocumentRule[Facts]
    | QueriedSkillRule[Facts]
    | QueriedMarkdownRule[Facts]
    | QueriedSkillFileRule[Facts]
    | QueriedFrontmatterRule[Facts]
)


def _judged_item[Facts](
    rule: type[ItemQueriedRule[Facts]], database: Database, ref: MarkdownItemRef
) -> tuple[Rule, ...]:
    """Judge one item rule from the facts of its memoized query.

    Args:
        rule: The rule to run.
        database: The revision the query is resolved from.
        ref: The Markdown item whose query the database resolves.
    """
    facts = database.query(rule.query(), ref)
    return rule.judge(facts)


def _judged_symlink[Facts](
    rule: type[QueriedSymlinkRule[Facts]], database: Database, ref: SymlinkRef
) -> tuple[Rule, ...]:
    """Judge one symlink rule from the facts of its memoized query.

    Args:
        rule: The rule to run.
        database: The revision the query is resolved from.
        ref: The symlink whose query the database resolves.
    """
    return rule.judge(database.query(rule.query(), ref))


def _judged_corpus_directory[Facts](
    rule: type[QueriedCorpusDirectoryRule[Facts]], database: Database, ref: CorpusDirectoryRef
) -> tuple[Rule, ...]:
    """Judge one corpus-directory rule from the facts of its memoized query.

    Args:
        rule: The rule to run.
        database: The revision the query is resolved from.
        ref: The corpus directory whose query the database resolves.
    """
    return rule.judge(database.query(rule.query(), ref))


def _located[R: Rule](
    path: RootRelativePath, partition: tuple[EnabledRule[R], ...], judge: Callable[[type[R]], tuple[Rule, ...]]
) -> list[Diagnostic]:
    """Every occurrence of the partition's rules, each located at the path at its rule's severity, in code order.

    Args:
        path: Where the subject is reported.
        partition: The enabled rules of one base.
        judge: Runs one rule of the partition over the subject.
    """
    return [
        RuleDiagnostic(path, occurrence, enabled.severity)
        for enabled in partition
        for occurrence in judge(enabled.rule)
    ]


def check_layout_entry(
    entry: OutsideSymlink | ReservedCorpusDirectory, database: Database, table: RuleTable
) -> CheckedLayoutEntry:
    """Run the enabled rules over one layout entry, a symlink or a reserved-corpus directory. Raises nothing.

    Args:
        entry: The entry, as the model or a skill's resource listing records it.
        database: The revision whose model and resource listings resolve the subject ref.
        table: The rules the run enables.
    """
    # Layout facts use the database's typed query cache like facts for Markdown subjects.
    match entry:
        case OutsideSymlink():
            symlink = entry
            diagnostics = _located(
                entry.path,
                table.symlink_rules,
                lambda rule: _judged_symlink(rule, database, SymlinkRef(symlink.path)),
            )
        case ReservedCorpusDirectory():
            directory = entry
            diagnostics = _located(
                entry.path,
                table.corpus_directory_rules,
                lambda rule: _judged_corpus_directory(rule, database, CorpusDirectoryRef(directory.path)),
            )
        case _:
            assert_never(entry)

    return CheckedLayoutEntry(entry.path, diagnostics=tuple(diagnostics))
