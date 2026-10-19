"""The rules engine's shared runner: every enabled rule over a subject, through one rule table.

This is what every mode of the engine shares: the governance lookup, gate evaluation, and running
the table's rules over a subject into its report. It holds no mode's policy. A document, specification, skill
and resource are decoded by each mode's own entry point beside this module, `skip.check_subjects` for the check run,
so that its policy for an item a failed layer governs comes after decoding; the entry point hands the decoded item to
`judge_item` and the other subjects to the functions here.

The runner never names a rule. A rule joins its base's group in the table through the registry, and the runner
judges every rule of a group from its query's answer, so adding a rule never edits this module. What it names is
each subject kind, in one hand-written branch, so the queries stay typed; a new value a rule reads is a query of the
database, never a branch here.

Subject decoding precedes rule judgment. Each subject is decoded once: one that does not decode is reported as
`UndecodableSubject`, whatever the table enables, and no rule sees it. A decoded item is then judged group by
group: for each group of enabled rules that applies to its kind, the runner checks the rule's gate, runs the rules
whose gates admit the item, and records an ungoverned meta spec part as coverage rather than a diagnostic. A rule over a
Markdown file judges a document when its structure specification is loaded, alongside rules gated by a named
meta spec part. A document in no corpus, or in one that states no structure specification, has no such part
governed, and no such rule is run over it. Package checks judge skill entrypoints independently of corpus
governance. Package Markdown checks judge resources independently of corpus governance. A rule over a skill entrypoint
judges every `SKILL.md` and every resource, and never a document. The database answers only what a rule's query reads,
so a value no enabled rule reads is never computed.

The subjects are those of `skip.CheckedSubject`, which defines and dispatches them: documents, specifications, skills,
skills' resources and layout entries. A decoded document, skill or resource
is judged by the one entry `judge_item`; a layout entry has a function of its own, so a subject kind without one is a
type error. A document is handed over as its ref, and a skill as the `SkillLocation` the
model hands out for it, since a rule over a skill may read where its directory leads. A skill entrypoint is the
`SKILL.md`,
decoded and reported at that path, under its ref. A resource is a subject of its own, handed over as the
`SkillResourceLocation` its skill's resource listing gives, since only that listing locates its file: it is decoded at
the file it leads to, and reported under its ref, at the path an agent reaches it by, through the same item queries.
The runner never lists a skill's resources itself, so a skill handed over judges its `SKILL.md` alone.

A layout entry is one symlink of the skill layout whose chain leaves the repository, represented by its typed
`OutsideSymlinkRef`, or a directory under `docs/` named like a reserved corpus, represented by its typed
`ReservedCorpusDirectoryRef`. The caller collects the entries its selection covers, as it chooses every other subject,
from queries: the model's `outside_symlinks`, for a skills directory, an entry in one or an entry's `SKILL.md`, its
`sorted_overlapping_directories`, for a reserved-corpus directory, and the `skill_resources` listing of each skill it
checks whole, for a symlink inside that skill. Each is reported at the path an agent reaches it by, in the order given
like every subject. An entry has no text, so it is never decoded, and the package governs the layout, so it is never
ungoverned. The runner judges an entry through `Database.query` by its typed subject ref, so its answer is memoized
just like an item's.
"""

from collections.abc import Callable
from typing import assert_never, cast

from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import ReservedCorpusDirectory, ReservedCorpusDirectoryRef
from lorecraft.project.database import Database, ItemText
from lorecraft.project.item import ItemDescriptor, ItemRef, MetaSpecPart
from lorecraft.project.query import ItemQuery
from lorecraft.project.skill import OutsideSymlink, OutsideSymlinkRef
from lorecraft.project.workspace.model import WorkspaceModel
from lorecraft.rules.declaration import Rule
from lorecraft.rules.report import (
    CheckedItem,
    CheckedLayoutEntry,
    Diagnostic,
    RuleDiagnostic,
)
from lorecraft.rules.subject import (
    ByMetaSpec,
    ByPackage,
    BySchema,
    ItemRule,
    Queried,
    QueriedCorpusDirectoryRule,
    QueriedSymlinkRule,
)
from lorecraft.rules.table import EnabledRule, QueriedItem, RuleTable


def judge_item(database: Database, source: ItemText, table: RuleTable) -> CheckedItem:
    """Run enabled rules over a decoded document, specification, skill or resource.

    A mode decodes the item and decides what a layer that failed to load means for it; this judges it against the
    gates applicable to its kind. A rule judges an item only when its gate admits that item; an applicable enabled
    rule whose gate is not met is recorded as coverage. Nothing here asks where the item came from, so registering a
    rule under a new base needs no branch.

    Args:
        database: The revision the item is read from.
        source: The item's text, the witness every per-file query takes.
        table: The rules the run enables.
    """
    descriptor = source.descriptor
    model = database.model()
    diagnostics: list[Diagnostic] = []
    ungoverned: list[MetaSpecPart] = []

    # Meta spec parts follow `MetaSpecPart` order, then package/schema rules; unmet gates become coverage.
    for part in (*MetaSpecPart, None):
        rules = tuple(
            enabled for enabled in table.item_rules(descriptor.kind, part) if judges(enabled.rule, descriptor, model)
        )
        if not rules:
            continue
        if part is not None and part not in descriptor.governed_parts:
            ungoverned.append(part)
            continue
        diagnostics.extend(
            _located(descriptor.ref.path, rules, lambda rule: _judged_item(rule, database, descriptor.ref))
        )

    return CheckedItem(descriptor.ref, diagnostics=tuple(diagnostics), ungoverned=tuple(ungoverned))


def judges(
    rule: type[QueriedItem],
    descriptor: ItemDescriptor,
    model: WorkspaceModel,
) -> bool:
    """Whether the rule's gate admits this item and any required governance source.

    Args:
        rule: The queried rule whose gate is being checked.
        descriptor: The item kind and origin metadata used by the gate.
        model: The workspace state used to check registered schema gates.
    """
    # SAFETY: Every queried item rule is also an ItemRule; the table rejects other queried bases from item buckets.
    gate = cast(type[ItemRule], rule).GATES.get(descriptor.kind)
    if gate is None:
        return False
    match gate:
        case ByMetaSpec():
            return True
        case ByPackage():
            return True
        case BySchema(schema):
            return schema in model.schema_inputs
        case _:
            assert_never(gate)


def _judged_item[Facts](
    rule: type[Queried[Facts, ItemQuery[Facts]]], database: Database, ref: ItemRef
) -> tuple[Rule, ...]:
    """Judge one item rule from the answer of its memoized query.

    Args:
        rule: The rule to run.
        database: The revision the query is resolved from.
        ref: The Markdown item whose query the database resolves.
    """
    facts = database.query(rule.query(), ref)
    return rule.judge(facts)


def _judged_symlink[Facts](
    rule: type[QueriedSymlinkRule[Facts]], database: Database, ref: OutsideSymlinkRef
) -> tuple[Rule, ...]:
    """Judge one symlink rule from the answer of its memoized query.

    Args:
        rule: The rule to run.
        database: The revision the query is resolved from.
        ref: The symlink whose query the database resolves.
    """
    return rule.judge(database.query(rule.query(), ref))


def _judged_corpus_directory[Facts](
    rule: type[QueriedCorpusDirectoryRule[Facts]], database: Database, ref: ReservedCorpusDirectoryRef
) -> tuple[Rule, ...]:
    """Judge one corpus-directory rule from the answer of its memoized query.

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
    # Layout query answers use the database's typed cache like item query answers.
    match entry:
        case OutsideSymlink():
            symlink = entry
            diagnostics = _located(
                entry.path,
                table.symlink_rules,
                lambda rule: _judged_symlink(rule, database, OutsideSymlinkRef(symlink.path)),
            )
        case ReservedCorpusDirectory():
            directory = entry
            diagnostics = _located(
                entry.path,
                table.corpus_directory_rules,
                lambda rule: _judged_corpus_directory(rule, database, ReservedCorpusDirectoryRef(directory.path)),
            )
        case _:
            assert_never(entry)

    return CheckedLayoutEntry(entry.path, diagnostics=tuple(diagnostics))
