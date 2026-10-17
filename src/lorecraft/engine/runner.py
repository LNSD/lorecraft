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

The subjects are documents, skills, skills' resources and layout entries. A decoded document, skill entry or resource
is judged by the one entry `judge_item`; a layout entry has a function of its own, so a subject kind without one is a
type error. A document is handed over as its ref, and a skill as the `SkillLocation` the
model hands out for it, since a rule over a skill may read where its directory leads. A skill is its `SKILL.md`,
decoded and reported at that path, under its ref. A resource is a subject of its own, handed over as the
`SkillResourceLocation` its skill's resource listing gives, since only that listing locates its file: it is decoded at
the file it leads to, and reported under its ref, at the path an agent reaches it by, through the same item queries.
The runner never lists a skill's resources itself, so a skill handed over judges its `SKILL.md` alone.

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

from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import (
    Database,
    DatabaseItemContext,
    DatabaseSymlinkContext,
    ItemText,
)
from lorecraft.project.document import DocumentRef
from lorecraft.project.item import ItemFacet, MarkdownItemDescriptor
from lorecraft.project.skill import OutsideSymlink, SkillAliasRef, SkillLocation, SkillResourceLocation
from lorecraft.rules.declaration import Rule
from lorecraft.rules.report import (
    CheckedItem,
    CheckedLayoutEntry,
    Diagnostic,
    RuleDiagnostic,
)
from lorecraft.rules.subject import Facet, ItemRule, governing_facet
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


def judge_item(database: Database, source: ItemText, table: RuleTable) -> CheckedItem:
    """Run the enabled rules over a decoded document or skill entry, each over what the specifications govern it for.

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
    context = DatabaseItemContext(database, source)
    diagnostics: list[Diagnostic] = []
    ungoverned: list[Facet] = []

    # The facets are reached in `Facet` order, then the rules that read none; the ungoverned facets are recorded in
    # that order, and a facet no applicable enabled rule reads is never looked at.
    for facet in (*Facet, None):
        frontmatter_rules = _reading(table.frontmatter_rules, descriptor, facet)
        document_rules = _reading(table.document_rules, descriptor, facet)
        markdown_rules = _reading(table.markdown_rules, descriptor, facet)
        skill_rules = _reading(table.skill_rules, descriptor, facet)
        skill_file_rules = _reading(table.skill_file_rules, descriptor, facet)
        if not (frontmatter_rules or document_rules or markdown_rules or skill_rules or skill_file_rules):
            continue
        if facet is not None and ItemFacet(facet.value) not in descriptor.active_facets:
            ungoverned.append(facet)
            continue
        path = descriptor.ref.path
        diagnostics.extend(_located(path, frontmatter_rules, lambda rule: rule.check(context)))
        diagnostics.extend(_located(path, document_rules, lambda rule: rule.check(context)))
        diagnostics.extend(_located(path, markdown_rules, lambda rule: rule.check(context)))
        diagnostics.extend(_located(path, skill_rules, lambda rule: rule.check(context)))
        diagnostics.extend(_located(path, skill_file_rules, lambda rule: rule.check(context)))

    return CheckedItem(descriptor.ref, diagnostics=tuple(diagnostics), ungoverned=tuple(ungoverned))


def _reading[R: ItemRule](
    partition: tuple[EnabledRule[R], ...], descriptor: MarkdownItemDescriptor, facet: Facet | None
) -> tuple[EnabledRule[R], ...]:
    """The partition's rules that judge an item of the descriptor's kind and read the facet.

    Args:
        partition: The enabled rules of one base.
        descriptor: The item the rules would judge.
        facet: The facet the rules must read, or `None` for those that read none.
    """
    return tuple(
        enabled
        for enabled in partition
        if descriptor.kind in enabled.rule.APPLIES_TO and governing_facet(enabled.rule) is facet
    )


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


def check_layout_entry(outside: OutsideSymlink, table: RuleTable) -> CheckedLayoutEntry:
    """Run the enabled rules over one symlink of the skill layout whose chain leaves the repository. Raises nothing.

    Args:
        outside: The symlink, as the model or a skill's resource listing records it.
        table: The rules the run enables.
    """
    # The symlink has no text to decode, and the package governs the skill layout, so each rule over a symlink
    # judges it through its context, which reads the record and asks the database nothing.
    context = DatabaseSymlinkContext(outside)
    diagnostics = _located(outside.path, table.symlink_rules, lambda rule: rule.check(context))

    return CheckedLayoutEntry(outside.path, diagnostics=tuple(diagnostics))
