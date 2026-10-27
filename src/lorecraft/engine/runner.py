"""The rules engine's shared runner: every enabled rule over a subject, through one rule table.

This is what the engine shares: the governance lookup, gate evaluation, and running the table's rules over a subject
into its report. It holds no mode's policy. The check run in `skip.check_subjects` decodes item subjects and applies
its policy for failed layers before handing decoded items to `judge_item` and layout subjects to the functions here.

The runner never names a rule. A rule joins its base's group in the table through the registry, and the runner
judges every rule of a group from its query's answer, so adding a rule never edits this module. The database resolves
each rule's query for its subject, keeping query typing at that boundary; a new value a rule reads is a query, never
a runner branch.

Subject decoding precedes rule judgment. Each subject is decoded once: one that does not decode is reported as
`UndecodableSubject`, whatever the table enables, and no rule sees it. A decoded item is then judged group by
group: for each group of enabled rules that applies to its item type, the runner checks the rule's gate, runs the rules
whose gates admit the item, and records an ungoverned spec part as coverage rather than a diagnostic. A rule over a
Markdown file judges a document when its structure file is loaded, alongside rules gated by a named
spec part. A document in no corpus, or in one that states no structure file, has no such part
governed, and no such rule is run over it. `Always` checks judge only the explicitly mapped item types, independently of
corpus governance. Markdown checks over resources are `Always`-gated, so they judge resources independently of corpus
governance. A rule over a skill entrypoint
judges every `SKILL.md` and every resource, and never a document. The database answers only what a rule's query reads,
so a value no enabled rule reads is never computed.

The subjects are those of `skip.CheckedSubject`: documents, specs, skills, skill resources and layout entries. A
decoded document, skill entrypoint or resource is judged by `judge_item`; a layout entry has its own function, so a
subject kind without one is a type error. An item subject is identified for rule queries and diagnostics by its
`ItemRef`. A skill entrypoint is its `SKILL.md`; a skill resource is a separate item whose ref is the path an agent
reaches it by, while its descriptor retains where the snapshot reads it. Each is judged through the same item queries.
The runner never lists a skill's resources itself, so a skill judges its `SKILL.md` alone. A refused docs alias is
reported as coverage at the alias's own item ref, while the refusal is reported at its target.

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
from typing import Protocol, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import ReservedCorpusDirectory, ReservedCorpusDirectoryRef
from lorecraft.project.database import Database, ItemText
from lorecraft.project.item import ItemDescriptor, ItemRef, ItemType, SpecPart
from lorecraft.project.skill import OutsideSymlink, OutsideSymlinkRef
from lorecraft.rules.declaration import Rule
from lorecraft.rules.report import (
    CheckedItem,
    CheckedLayoutEntry,
    Diagnostic,
    RuleDiagnostic,
)
from lorecraft.rules.subject import (
    Always,
    Gate,
    QueriedCorpusDirectoryRule,
    QueriedItemRule,
    QueriedSymlinkRule,
    WhenSpec,
)
from lorecraft.rules.table import EnabledRule, QueriedItem, RuleTable


class ItemRuleLookup(Protocol):
    """The item-rule lookup the shared judge needs from a run's rule table."""

    def item_rules(self, item_type: ItemType, gate: Gate) -> tuple[EnabledRule[QueriedItem], ...]:
        """Each enabled rule for an item type and applicability gate."""


def judge_item(
    database: Database,
    source: ItemText,
    table: ItemRuleLookup,
) -> CheckedItem:
    """Run enabled rules over a decoded document, spec, skill or resource.

    A mode decodes the item and decides what a layer that failed to load means for it; this judges it against the
    gates applicable to its item type. A rule judges an item only when its gate admits that item; an applicable enabled
    rule whose gate is not met is recorded as coverage. Nothing here asks where the item came from, so registering a
    rule under a new base needs no branch.

    Args:
        database: The revision the item is read from.
        source: The item's text, the witness every per-file query takes.
        table: The rules the run enables.
    """
    descriptor = source.descriptor
    diagnostics: list[Diagnostic] = []
    ungoverned: list[SpecPart] = []

    # Spec parts follow `SpecPart` order, then `Always` rules; unmet gates become coverage.
    for gate in (*(WhenSpec(part) for part in SpecPart), Always()):
        rules = tuple(
            enabled for enabled in table.item_rules(descriptor.type, gate) if judges(enabled.rule, descriptor)
        )
        if not rules:
            continue
        part = gate.part if isinstance(gate, WhenSpec) else None
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
) -> bool:
    """Whether the rule's gate admits this item.

    Args:
        rule: The queried rule whose gate is being checked.
        descriptor: The item type and origin metadata used by the gate.
    """
    gate = rule.APPLIES_TO.get(descriptor.type)
    if gate is None:
        return False
    match gate:
        case WhenSpec():
            return True
        case Always():
            return True
        case _:
            assert_never(gate)


def _judged_item[Facts](rule: type[QueriedItemRule[Facts]], database: Database, ref: ItemRef) -> tuple[Rule, ...]:
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
        RuleDiagnostic(path, occurrence, enabled.resolution)
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

    match entry:
        case OutsideSymlink():
            ref = OutsideSymlinkRef(entry.path)
        case ReservedCorpusDirectory():
            ref = ReservedCorpusDirectoryRef(entry.path)
        case _:
            assert_never(entry)
    return CheckedLayoutEntry(ref, diagnostics=tuple(diagnostics))
