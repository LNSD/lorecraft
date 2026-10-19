---
name: "adr-011-rules-engine"
description: "How a run of the structured checks judges subjects: a rule table built from the registry, the levels and a one-run selection, a query per rule whose facts are memoized primitives, a decoded subject before any rule, one runner, and caching in memory for one revision. Load when adding a rule base or a query a rule reads, changing how subjects are selected or levels resolved, or reasoning about what a run costs"
type: "adr"
status: "accepted"
---

# Rules Engine: Running the Rules

> [!NOTE]
> Superseded in part: the per-kind content references, decode witnesses and runner loops, and the subject contexts a
> rule reads its facts through. The text below states the query design in their place, where it spoke of them. The
> rest of this record binds code.

This record is one of three that state how the structured checks of [prd-008](prd-008-structured-checks.md) are
built: [adr-009](adr-009-rules.md) how a rule is declared and identified, [adr-010](adr-010-diagnostics.md) what a
rule reports and how it reaches the user, and [adr-011](adr-011-rules-engine.md) how a run judges subjects.
Requirement identifiers such as `FR-009` cite the PRD, and the terms are those of [adr-009's
glossary](adr-009-rules.md#glossary). Names of types, modules, codes and prefixes in the sketches are illustrative;
the shapes are the decision. Which rules exist, and which base and facet each takes, is the registry's and the
rulebook's to say, never this record's.

## Context

Lorecraft already has the right foundation. A `Database` wraps one revision and memoizes every derived
value as a query. A check is a pure function of the values those queries return, and it returns violations that
name no document. The engine keeps all of that.

What it replaces is everything around the checks:

- **Four pipelines.** `checks/run.py` holds one `run_*` function per check. Each resolves its own inputs, and
  documents and skills report through parallel types: `CheckRun` and `SkillCheckRun`, and a report type each for
  a document, a skill, a resource and a symlink.
- **Facts read once per check.** A file that is not UTF-8 is decoded, and reported, once per check.
- **Uncached cross-file lookups.** The link rules read `find_path`, which is answered fresh on every call and
  states no carry-over rule.
- **No levels.** Every finding fails the run.

## Decision

1. **A rule names its query and judges the facts it returns** and, over a document, declares the facet it is
   governed for. A rule may walk the parse tree its facts hold, but a pass over a file's raw text or a schema
   is a query, and so is a walk several rules share. A helper that only selects from a value the facts already
   hold, such as the first H1 among the parsed headings, is not such a walk, so it stays a function beside the parse
   tree. An analysis several rules share is a query of the database, never a rule with several codes.
2. **One runner** resolves each rule's query for a subject through the database and hands the facts to the rule's
   judgement, with one hand-written branch per subject kind. A query asks the database only for what a rule reads.
3. **A subject's status is the engine's, not a rule's.** Whether a file decodes, and whether a meta spec
   governs each facet, is resolved before any rule runs.
4. **Levels are applied after detection.** The configuration is an input of the revision, and a rule's result
   never depends on it.
5. **The engine is efficient within one revision**, caching in memory and persisting nothing across runs.

## Design

### Overview

The engine is generic over rules and specific over subject kinds. The set of rules is fixed by the package, then
filtered and graded before a run; the run then judges each selected subject through the queries its rules name.

```text
once per process   registry ── walks rules/, collects every @rule class (package data)
                       │
per run            configuration (a query of the revision) ──▶ levels
                   --select / --ignore ──────────────────────▶ selection
                       │
                       ▼
                   rule table = registry × levels × selection
                     · enabled rules only (allow and filtered-out rules are absent)
                     · each with its severity
                     · partitioned by base, a document's rules also by facet, in code order
                     · a bad configuration is raised here, before any subject
                       │
                       ▼
                   runner(database, subjects, table)
                     for each subject:
                       decode → witness, or an undecodable engine diagnostic
                       decode once; each rule's query runs over the item
                       for each facet an enabled rule over a document declares:
                         governed or ungoverned, from the meta specs
                         for each rule in that partition: rule.judge(facts of rule.query()) → occurrences
                       locate the occurrences into diagnostics with the table's severities
                       │
                       ▼
                   subject reports → command line renders text / JSON, exit code
```

- **Generic over rules.** The runner never names a rule: a new rule is a class the registry collects, and it
  joins its base's partition of the table.
- **Specific over subject kinds.** The runner has one hand-written branch per subject kind, which keeps dispatch
  typed: the document partition holds `type[DocumentRule]`, so `rule.judge(facts)` checks against
  the facts its query returns.
- **Configuration and selection never reach a rule.** They shape the table and nothing else.
- **Subjects arrive chosen.** The command line chooses the subjects, the whole workspace until paths arrive; the
  runner receives a document's ref or a skill's location as the model issued it, a resource's location as its
  skill's resource listing issued it, or a layout entry's record as the model or that listing issued it, the
  database and the table, and nothing else.

### Queries

A rule reads the facts of one query, a pure function over the primitives of one decoded subject, and nothing else:
never the database, a view or a path. Each primitive is a memoized query of the database, or an identity value read
from the subject's ref or location, such as a filename or the directory a skill is listed under. So a rule pulls only
what it reads, and a fact no enabled rule reads is never computed. A document's governance is the
`item_governance(ref)` query, carried over when the next model's governance of the ref compares equal. Three rules
follow.

**A query scans, a rule loops.** The cost of a run lies in the queries: the parse, and the shared analyses over it. A
rule's own work is a loop over a short tuple a query returned, or a walk of the parse tree it alone reads. A scan
written inside a rule is paid once per rule, and the same scan written as a query is paid once per subject, however
many rules read it, so a scan two rules need is a query. A new fact is one query a rule names, whose carry-over
is derived from the primitives it read: that is where a new cost enters and is reviewed, and the runner never changes for it.

**A shared analysis is a query.** Schema validation and outline matching each find several conditions in one
pass. Each is a pure function of the revision's per-file queries and the meta specs that govern the subject, so
it is memoized on the database like any other query, with its own carry-over rule: `item_schema_problems` is kept
whenever the frontmatter is and, for a document, the model is, and
`outline_divergences` whenever the parse and the line count are and the model is. It is computed once per subject,
as a tuple of typed problems, however many rules ask for it, and only when an enabled rule reads it and a
meta spec governs the subject for it, so an ungoverned subject never pays for it. Each condition is then a rule
that projects its own problem type into its occurrences. The analysis finds problems, never diagnostics: levels are
applied after detection, so no diagnostic is cached and a rule's result still is not.

**A cross-file fact is a query.** The link-target states are a query keyed by the subject's ref, one per kind of
Markdown file, read as the `item_link_targets` primitive: what the snapshot holds at the target of each relative link,
present, missing or outside the scope the scan read, with the root-relative path it was looked up at, keyed by the
link's normalised relative path. Each link is read from the file's `link_base` primitive, the skill root for any file
of a skill and the document's own directory for a document, and a link climbing past that bound has no entry. A
document's links to other documents, with each one's corpus and whether it links back, are the `document_links`
primitive. The query states facts; whether a missing target makes a link broken is the rule's. Its carry-over rule
names every path it looked up, an absent target included, since creating a missing target must remove its diagnostic.
Nothing a rule reads is left outside a query contract.

**A subject's facts are the query's.** `lorecraft.project.query` declares the primitives a query reads as focused
protocols, and a rule base per subject kind types its query and its judgement by the facts it returns, with a base
for what several kinds share: any one Markdown file, one of a skill's files, and the frontmatter of a document and a
skill alike. A rule over a document declares the facet it reads in `GOVERNED_BY`: a frontmatter schema, the structure
file its corpus states, an outline, or a token budget. A rule over the frontmatter inherits the frontmatter facet from
its base, so the runner gates it on a document as it gates a rule over a document, and a skill is governed for it by
the package. A rule over a Markdown file judges a document under its structure, and every skill entrypoint, which the
package governs; a rule over a skill's file or a layout entry declares no facet. A rule over a shared analysis
filters its own problem type out of the one answer the query gives; a selection from a value the facts already hold,
such as the first H1, is a helper beside the parse tree.

**A layout entry is read through a query over its record**, since it has no text. One layout entry is one symlink of
the skill layout whose chain leaves the repository: a skills directory, an entry in one or an entry's `SKILL.md`, from
the model's outside symlinks, or a symlink inside a skill, from that skill's resource listing. The loader and the
resource walk decide that a chain leaves, from the link targets the scan recorded, so a symlink that stays or dangles
inside is no entry. `SymlinkPrimitives` and `CorpusDirectoryPrimitives` state where the chain leaves, a fact and never a
verdict, from the record those queries returned. A rule over an entry derives from `LayoutRule`, through
`QueriedSymlinkRule` or `QueriedCorpusDirectoryRule`, and only words the finding, at the path an agent reaches the
symlink by. A symlink has no text, so it is never decoded, and the package governs the layout, so it is never ungoverned.

### A Subject's Status Comes Before Any Rule

- **Readable or undecodable.** A file is decoded once, as a query value: its text, or an undecodable marker,
  cached like any result. The runner decodes every selected subject, whatever the levels. That is the one read
  NFR-003 does not gate, so that FR-020 holds under any configuration.
- **Governed or ungoverned, per facet.** Governance comes from the model, which computes it once. A document can be
  governed for its frontmatter and ungoverned for its outline. The runner runs a rule over a document or over the
  frontmatter only when the document is governed for the rule's facet, and records each facet an enabled rule reads
  that it is not governed for. A skill and a resource are governed by the package for every facet, so neither is ever
  ungoverned.
- **Undecodable is an engine diagnostic**, not a rule (FR-020). It has a fixed code under the engine's prefix
  and a rulebook page, and no level. It always fails the run, and a configuration that names its code fails.
- **Ungoverned is coverage**, not a diagnostic (FR-019). It describes the meta specs, not the subject.

Decoding is a type boundary, as it is in established linters, which report a file they cannot read as the
engine's diagnostic and hand their rules only a value that exists after a successful read. Three traits are
required:

- **Decoded once, at one boundary.** The decode query is the only place a subject's bytes become text.
- **The failure is the engine's**, never a rule's, as above.
- **Nothing can ask for an undecodable subject's facts.** A successful decode returns a witness, a value holding
  the subject's ref and its decoded text, one type per subject kind. Every per-file query takes the witness, not
  the ref, and keeps its cache keyed by the ref. Asking for a fact with a bare ref, or with the undecodable
  marker, is a type error, so the runner matches the decode once and no later reader carries a branch for it.

Python's types bound what this proves, and the design states the two gaps rather than guard them:

- **A witness can be forged**, since Python has no private constructor. Forged text is still text, so what it
  breaks is that the text is this ref's bytes, not that it decodes. Only the database builds a witness, as only
  the view builds a `ResolvedPath`.
- **A witness belongs to the revision that produced it**, and no Python type ties it to one database. It never
  leaves the runner's locals and never enters a diagnostic or a report, so one revision per run cannot mix two.

### The Runner

The runner takes the database, the selected subjects and a rule table. The table is built once per run from the
registry and the resolved levels: the enabled rules, partitioned by base, in code order, and a document's rules
also by facet. Each partition holds every enabled rule beside its severity, so a rule the runner holds always
has one. For a document, the runner runs, for each facet an enabled document rule declares, and the
frontmatter facet when a frontmatter rule is enabled, those rules' queries and judgements, or records the facet as
ungoverned; the Markdown rules run beside the `STRUCTURE` rules. For a skill, it runs every
frontmatter rule, then every skill rule, every Markdown rule and every skill-file rule. For a resource, it
runs every Markdown rule and every skill-file rule. For a layout entry, it runs every layout rule over the query of
the entry's record, in a report that holds the entry's path and its
diagnostics.

```python
def judge_item(database: Database, source: ItemText, table: RuleTable) -> CheckedItem:
    descriptor = source.descriptor
    diagnostics: list[Diagnostic] = []
    ungoverned: list[Facet] = []

    for facet in (*Facet, None):
        partitions = [
            _reading(partition, descriptor, facet)
            for partition in (
                table.frontmatter_rules,
                table.document_rules,
                table.markdown_rules,
                table.skill_rules,
                table.skill_file_rules,
            )
        ]
        if not any(partitions):  # a facet no applicable enabled rule reads is never looked at
            continue
        if facet is not None and ItemFacet(facet.value) not in descriptor.active_facets:
            ungoverned.append(facet)
            continue
        for rules in partitions:
            for enabled in rules:
                facts = database.query(enabled.rule.query(), descriptor.ref)  # the query reads only what the rule needs
                for occurrence in enabled.rule.judge(facts):
                    diagnostics.append(RuleDiagnostic(descriptor.ref.path, occurrence, enabled.severity))
    ...
    return CheckedItem(descriptor.ref, diagnostics=tuple(diagnostics), ungoverned=tuple(ungoverned))
```

- **Adding a rule never touches the runner.** The rule joins its base's partition through the registry
  (NFR-004).
- **Adding a fact never touches it either**: one query a rule names. That is
  the deliberate point where a new dependency is reviewed.
- **A rule at `allow` is not in the table**, so it does not run and what it reads may never be computed (FR-027,
  NFR-003).
- **No second walk.** Every subject kind goes through the same function family and the same table. A new group
  or subject kind adds no pipeline.

### Levels, Configuration and Selection

- **Three levels**, `allow`, `warn` and `deny`, with a default on each class (FR-023).
- **The configuration file is designed apart from this document**: where it lives, its format and how it is
  found. Until it lands, every rule runs at its default level, and the rule table is built from the registry,
  those defaults and the selection. Whatever its location and format, the file holds to the contract below: it
  holds levels and nothing else, never a rule's options; it is read through the snapshot, as a database query
  whose carry-over rule is the file's location and bytes; and it is decoded at the edge into a strict, closed,
  typed model, every key a `RuleCode | RuleGroup` and every value a `Level`, so nothing past the edge reads a raw
  string.
  Whether a run can fail on warnings is decided with the file and the level options on the command line; until
  then a run fails on errors alone (FR-026).
- **Resolution order:** the class's default, then a setting by prefix, then a setting by code (FR-024). An
  unknown code, prefix or level is a failure before any subject is checked (FR-025). An alias code resolves to
  its rule's code, with an engine diagnostic at warning on the configuration file naming the code to write. A
  configuration that sets one rule under both its code and an alias code is a failure, so one rule never has two
  settings.
- **A one-run selection filters; it never changes a level** (FR-008). `--select` and `--ignore` take `ALL`, group
  prefixes, code prefixes of one or two digits and codes, alias codes resolving with a warning naming the code to
  write, and narrow which rules run in this run. They refuse a rule's name, the `LC` group, an engine condition and a
  removed rule, since none can narrow a run. As in ruff, the most specific selector matching a rule decides, `--ignore` winning a tie.
  There is no level option on the command line: levels live in the configuration alone, so a local run and CI agree
  on one revision (NFR-001). A rule at `allow` that the selection names by its code stays off, with a warning saying
  the selection does not enable it; one kept only through `ALL`, its group or a code prefix stays off silently,
  since the selection did not name it. Both warnings go to stderr, not into the report: they concern the command line, not a subject, so they
  have no path a diagnostic could be filed under. The established linters' `--select` enables a rule, because they
  have no levels; with levels, enabling a rule is the configuration's, and this is a stated departure.
- **A selection is typed at the boundary.** A selector is parsed while the command line is read, and confirmed
  against the rule index of [adr-009](adr-009-rules.md#the-index), before the engine loads. A malformed one, which has
  the shape of no selector, and an unknown one, which names nothing, are each a usage error that exits 2, never a
  filter that matches nothing (FR-025). When the command runs, a selector converts to `AllRules | RuleGroup |
  RuleCodePrefix | RuleCode`. No
  `--select` is `{AllRules()}`, never an empty set, which keeps no rule. The selection reaches the runner only as a
  filter on the rule table, so no rule runs around it.
- **Detection never reads the configuration.** Two rules that overlap are made disjoint in their own logic. The
  name rule compares `name` only when it is a string, so a missing or mistyped `name` belongs to the schema
  rule alone (FR-022).
- **A rule's options are meta spec data**, read through the primitives its query reads: a line length or a list marker style is
  stated beside the outline and caps, so corpora can differ. The established linters read rule options from
  their settings; this design departs from them because a rule that read the configuration would break the
  invariant above.
- **What a path selects stays in the command line**, which chooses the subjects (FR-002 to
  FR-007). For now the command checks the whole workspace and takes no path: selection by path, the next two
  bullets, is deferred. The runner receives subjects, sorted by
  path. The selection bounds what is reported, not what is read: a selected skill's link rule still reads the
  target it links to.
- **A file selects every subject it is, and a directory every subject under it** (FR-003, FR-004), as the
  established linters read a path, and as editor and pre-commit integrations expect when they pass the changed
  files. A document selects itself; a `SKILL.md` selects its skill as a subject, and none of its resources; a
  resource file selects that resource alone; a file several subjects lead to, such as a resource two skills
  link in, selects each of them once. A path is read as an agent sees it: a resource through the spelling of the
  skill that lists it, with symlinks transparent. A skill's directory is every subject under it, so the whole
  skill needs no scope flag of its own, and today's `SkillScope` goes.
- **A layout diagnostic is reported when the selection covers its entry** (FR-007): with no path, every one; with
  a directory, every entry under it as agents see it; and with a path that runs through the entry, that entry,
  so a path through a symlink leading outside reports the symlink rather than failing as naming no subject. One
  changed document checked alone never reports a skill symlink it did not touch.
- **What a path covers is decided at the boundary**, in the command line, and held by tests: it is arithmetic over
  user input, which no type expresses. What leaves the boundary is typed: the selection is a closed union of
  subject refs, which the runner matches with `assert_never`, so a subject kind without a branch is a type error.

### Where the Code Lives

| Piece | Package |
|---|---|
| Rule classes and removed rules, the registry, the rule groups and their rules, the rule bases per subject kind and the facets | `lorecraft.rules` |
| The rule table, the report types, the selection's rule-side types, level resolution | `lorecraft.rules` |
| The runner, which resolves each rule's query and hands the facts to its judgement | `lorecraft.engine` |
| Each mode's policy for a document a failed layer governs: skip for the check run, partial for the LSP-style mode | `lorecraft.engine` |
| The query types and the primitive protocols, what can be asked of one decoded subject | `lorecraft.project.query` |
| The database, decoding, the primitives' implementation ([adr-012](adr-012-database-derivation.md)) | `lorecraft.project.database` |
| The configuration file's dialect and its decoding, once it is designed | `lorecraft.project` |
| Path selection, options and their parsing against the rule index, text and machine-readable rendering, the exit code, the rule lookup command | `lorecraft.cli` |

`lorecraft.rules` is a layer of its own, below `lorecraft.engine` and above `lorecraft.project`. A forbidden contract
refuses a rule that imports `lorecraft.project.database`, so a rule cannot reach the database by import, which the
design could otherwise only state.

### Tests

- **A sample rule** is registered over an existing rule base in a test and runs with no other edit (NFR-004).

### Performance

The engine is efficient within one revision: no query is computed twice, no fact is asked for by a rule that does
not run, and a scan is paid once per subject whatever the number of rules. Caching stays in memory, in the
database, for the revision's lifetime. No result persists across runs in this release (see
[Deferred](#deferred)).

The baseline is v0.2 on this repository. Under a profiler, parsing Markdown, loading the tokenizer's vocabulary and
imports take most of a run, and the checks' own logic barely registers. So the number of rules is not the cost, and
the queries are.

Two measurements keep that true:

- **Before and after**, for NFR-002 and its margin over v0.2. The comparison is the median of repeated
  runs of both on one machine, with the noise stated; where it is close, the stages are timed apart on this
  repository: start-up, the snapshot, meta spec loading, decoding, parsing, token counting, schema validation, the
  rules and the rendering. Query counts show that no query is computed twice for a subject. Start-up is kept apart
  from the engine, so a command that runs no rule loads none of it.
- **At scale.** The cost per added rule stays small and flat: many synthetic rules over the existing queries add
  a few milliseconds to a run, as measured for this design. A slope that jumps means a query is computed per rule
  or a rule scans. A `just` recipe that repeats the measurement on demand is
  deferred until a change to the runner or the queries calls for it; it would be a recipe, not a test with a time
  limit, which a shared machine makes flaky.

One cost sits outside the engine and is a change of its own, after this one: the frontmatter query runs the
Markdown parser, so each document is parsed twice. Reading the frontmatter by its fences instead keeps the query
apart from the parse, as early cutoff needs, and must recognise frontmatter exactly as the parser does.

A more elaborate engine waits for a profile that asks for one.

## Alternatives Considered

- **One generic rule type, or a visitor over a syntax tree.** A rule reads a few facts of one subject, mostly
  short tuples, and loops over them on its own. One base per subject kind, which the runner matches on, stays typed
  and readable.
- **Undecodable and ungoverned as rules.** A rule can be turned off. A file that cannot be read must not be,
  and a missing meta spec is not a fact about the document.
- **Caching a subject's diagnostics as a query.** Not needed while rules are cheap and a run is one revision.

## Consequences

- **The per-check subcommands go.** One `check` command runs every rule over the workspace, and over the files
  and directories it is given once selection by path lands.
- **Specs change in the same change**, since each states something this design makes untrue:
  [module-lorecraft-engine](../code/module-lorecraft-engine.md) (the runner) and
  [adr-015-database](adr-015-database.md) (decoding as a value, cross-file queries).
- **A projecting rule is thin.** A schema rule is a few lines over a problem type, and the validation it
  projects lives in a query.
- **The runner is hand-written per subject kind.** That is the price of typed dispatch with no generic machinery.
- **The database sits apart from the linter**, as the established linters keep it. The rules, with the rule
  table, the selection and the report, sit in `lorecraft.rules`, the runner in `lorecraft.engine`, and the
  database, with its witnesses and the primitives' implementation, in `lorecraft.project.database`, beside the
  derivations it memoizes ([adr-012](adr-012-database-derivation.md)). The split adds no layer to the import
  contract.
- **What stays true:** a check is pure, a rule's result is never cached, and every value a rule reads comes from a
  query with a stated carry-over rule.

## Deferred

The PRD defers the IDE-like, long-lived mode. The design builds none of it and closes none of it off.

| Deferred | What the design keeps open |
|---|---|
| Re-checking only what a change affects | A rule names its query, whose carry-over is derived from the primitives it read, so the affected rules are derivable, a document's governance being recorded by `item_governance(ref)`; the long-lived mode's own entry point beside the check run's chooses what to re-check, and the shared runner does not change |
| Unsaved content | A rule reads values, never the disk |
| Rejecting a superseded revision's results | One report reads one revision; a diagnostic names no revision-bound object; the long-lived mode's own entry point abandons a superseded revision, and the shared runner does not change |
| Warm starts | No store is built: caching is in memory, for one revision. Query results stay persistable data, the new queries included, and the registry stays out of them, so the store of [adr-005-incremental](adr-005-incremental.md) is an addition. A cross-file query's carry-over rule names the paths it looked up; recording them waits for the store or for the next revision's carry-over |
| Cached diagnostics | Levels are applied after detection, so a cached result would not depend on the configuration |
| Inline suppression | Its shape is fixed, its syntax Lorecraft's own and modelled on the HTML-comment directives of the Markdown linters, with no compatibility with theirs: `<!-- lorecraft-disable CODE … -->` and `lorecraft-enable` around a block, and `lorecraft-disable-line`, `lorecraft-disable-next-line` and `lorecraft-disable-file`. A directive names its codes, never none, and never a name; an alias code resolves to its rule's code, with a warning. There is no state capture and no in-file configuration: options are meta spec data and levels are the repository's. The directives are a per-file query, applied after detection where levels are. A directive naming an unknown code, or one that suppressed nothing, is an engine diagnostic, and no engine diagnostic can be suppressed |
| Parallel checking | Output order is sorted, never completion order; the cache is still filled from one thread; the loop is the entry point's, and the shared runner does not change |
| Level options on the command line | Rustc-style flags that set a rule's level for one run, over the configuration's, reopen the no-level-option rule above, designed with the configuration |

## Checklist

Before committing code, verify:

- [ ] A rule reads only the facts its query returns: never the database, a view, a path or the disk
- [ ] A scan two rules need, an analysis several rules share and a cross-file fact are queries with a carry-over
  rule, reached through a query a rule names, and never a rule with several codes
- [ ] A new rule joins its base's partition through the registry, and the runner does not change for it
- [ ] Every per-file query takes the decode witness, and only the database builds one
- [ ] A file that cannot be decoded is an engine diagnostic and a facet no meta spec governs is coverage, both
  resolved before any rule runs
- [ ] A rule at `allow` is not in the rule table, and a selection only filters it, never enabling a rule
- [ ] Neither a rule nor its detection reads the configuration or the selection; levels apply after detection
- [ ] A selector is parsed and confirmed against the rule index at the command line's edge, and a bad one is a
  usage error
- [ ] Caching is in memory, in the database, for one revision; no result persists across runs
- [ ] No module of `lorecraft.rules` imports `lorecraft.project.database`

## References

- [prd-008-structured-checks](prd-008-structured-checks.md) - Source: The requirements this design answers
- [adr-009-rules](adr-009-rules.md) - Foundation: The rules the engine runs, and the glossary
- [adr-010-diagnostics](adr-010-diagnostics.md) - Related: What a run reports
- [adr-015-database](adr-015-database.md) - Foundation: Revisions and queries
- [adr-005-incremental](adr-005-incremental.md) - Foundation: Carry-over rules and persistable results
- [adr-016-specifications](adr-016-specifications.md) - Foundation: Governance, computed once by the model
- [adr-012-database-derivation](adr-012-database-derivation.md) - Foundation: The database in the Derivation package
- [module-lorecraft-engine](../code/module-lorecraft-engine.md) - Foundation: The package the runner lives in
