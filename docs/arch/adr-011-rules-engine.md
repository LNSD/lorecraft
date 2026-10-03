---
name: "adr-011-rules-engine"
description: "How a run of the structured checks judges subjects: a rule table built from the registry, the levels and a one-run selection, a closed set of inputs each built once per subject from the database's queries, a decoded subject before any rule, one runner, and caching in memory for one revision. Load when adding an input or a query a rule reads, changing how subjects are selected or levels resolved, or reasoning about what a run costs"
type: "adr"
status: "proposed"
---

# Rules Engine: Running the Rules

This record is one of three that state how the structured checks of [prd-008](prd-008-structured-checks.md) are
built: [adr-009](adr-009-rules.md) how a rule is declared and identified, [adr-010](adr-010-diagnostics.md) what a
rule reports and how it reaches the user, and [adr-011](adr-011-rules-engine.md) how a run judges subjects.
Requirement identifiers such as `FR-009` cite the PRD, and the terms are those of [adr-009's
glossary](adr-009-rules.md#glossary). Names of types, modules, codes and prefixes in the sketches are illustrative;
the shapes are the decision.

## Context

The checks package already has the right foundation. A `Database` wraps one revision and memoizes every derived
value as a query. A check is a pure function of the values those queries return, and it returns violations that
name no document. The engine keeps all of that.

What it replaces is everything around the checks:

- **Four pipelines.** `checks/run.py` holds one `run_*` function per check. Each resolves its own inputs, and
  documents and skills report through parallel types: `CheckRun` and `SkillCheckRun`, and a report type each for
  a document, a skill, a resource and a symlink.
- **Facts read once per check.** A file that is not UTF-8 is decoded, and reported, once per check.
- **Uncached cross-file lookups.** The link and `metadata` rules read `find_path`, `find_file` and
  `is_in_scope`, which are answered fresh on every call and state no carry-over rule.
- **No levels.** Every finding fails the run.

## Decision

1. **A closed set of input kinds.** A rule declares the one input it reads. An input scans, a rule loops: every
   pass over text, a tree or a schema is an input, and a rule only loops over the values its input holds. An
   analysis several rules share is an input of its own, never a rule with several codes.
2. **One runner** resolves each input once per subject, only when an enabled rule reads it, with one
   hand-written branch per input kind.
3. **A subject's status is the engine's, not a rule's.** Whether a file decodes, and whether a specification
   governs each input, is resolved before any rule runs.
4. **Levels are applied after detection.** The configuration is an input of the revision, and a rule's result
   never depends on it.
5. **The engine is efficient within one revision**, caching in memory and persisting nothing across runs.

## Design

### Overview

The engine is generic over rules and specific over inputs. The set of rules is fixed by the package, then
filtered and graded before a run; the run then judges each selected subject once per input kind.

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
                     · partitioned by input kind, in code order
                     · any failure (unknown code, bad config) is raised here, before any subject
                       │
                       ▼
                   runner(database, subjects, table)
                     for each subject:
                       decode → witness, or an undecodable engine diagnostic
                       for each input kind with enabled rules:
                         build the input once from the queries → governed or ungoverned
                         for each rule in that partition: rule.check(input) → violations
                       locate the violations into diagnostics with the table's severities
                       │
                       ▼
                   subject reports → command line renders text / JSON, exit code
```

- **Generic over rules.** The runner never names a rule: a new rule is a class the registry collects, and it
  joins its input's partition of the table.
- **Specific over inputs.** The runner has one hand-written branch per input kind, which keeps dispatch typed:
  the headings partition holds `type[HeadingsViolation]`, so `rule.check(input)` checks against `HeadingsInput`.
- **Configuration and selection never reach a rule.** They shape the table and nothing else.
- **Subjects arrive chosen.** The command line resolves the paths into subject refs; the runner receives those,
  the database and the table, and nothing else.

### Inputs

An input is a frozen value of Lorecraft's own types: the facts a query returned, the specifications that govern
them, and the subject's identity values, such as a filename or the directory a skill is listed under. A rule
receives one input and nothing else: never the database, a view or a path.

The set is closed. Each kind is one dataclass and one violation base class whose `check` takes it.

| Input | Subjects | Built from | Governed by |
|---|---|---|---|
| Frontmatter block | document, skill | the frontmatter query | a frontmatter schema |
| Schema problems | document, skill | the same query, and each governing schema | a frontmatter schema |
| Headings | document | the parse query | a structure specification |
| Outline divergence | document | the parse query, and each specification's outline | a structure specification |
| Token count | document | the tokens query | a specification that sets a budget |
| Line count | skill | the line-count query | the package |
| Links | skill, skill resource | the parse query, the link-target query, the skill's `metadata` | the package |
| Listed files | skill | the frontmatter query, the listed-file query | the package |
| Layout | layout entry, skill | the model, the skill's resource listing | the package |

Three rules follow from the table.

**An input scans, a rule loops.** Building an input is where the cost of a run lies: the parse, the token count,
the schema validation. A rule's own work is a loop over a short tuple the input prepared. So a scan written
inside a rule is paid once per rule, and the same scan written as an input is paid once per subject, however
many rules read it. A rule never walks text or a tree: the scan it needs is an input, existing or new. A rule
that needs two facts, such as the headings and the frontmatter, gets one input that holds both, never two
inputs. A new input is the runner's one reviewed extension point, so it is where a new cost enters and is
reviewed.

**A shared analysis is an input.** Schema validation and outline matching each find several conditions in one
pass. The runner computes the analysis once per subject, as a tuple of typed problems, when an enabled rule
reads it. Each condition is then a rule that projects its own problem type into its violation class. The
analysis is a judgment, so it lives for one run and is never memoized as a query: the invariant that check
results are not cached stands.

**A cross-file input is a query.** The link-target states and the listed-file states become queries keyed by the
subject's ref. Each one's carry-over rule names every path it looked up, an absent target included, since
creating a missing target must remove its diagnostic. Nothing a rule reads is left outside a query contract.

### A Subject's Status Comes Before Any Rule

- **Readable or undecodable.** A file is decoded once, as a query value: its text, or an undecodable marker,
  cached like any result. The runner decodes every selected subject, whatever the levels. That is the one read
  NFR-003 does not gate, so that FR-020 holds under any configuration.
- **Governed or ungoverned, per input kind.** Governance comes from the model, which computes it once. A document
  can be governed for its frontmatter and ungoverned for its outline. A rule only ever receives a governed input.
- **Undecodable is an engine diagnostic**, not a rule (FR-020). It has a fixed code under the engine's prefix
  and a rulebook page, and no level. It always fails the run, and a configuration that names its code fails.
- **Ungoverned is coverage**, not a diagnostic (FR-019). It describes the specifications, not the subject.

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
registry and the resolved levels: the enabled rules, partitioned by input kind, in code order.

```python
def _check_document(database: Database, ref: DocumentRef, table: RuleTable) -> SubjectReport:
    source = database.text(ref)
    if isinstance(source, Undecodable):
        return UndecodableSubject(ref)
    # `source` is a `DocumentText` from here on: the witness every per-file query takes

    violations: list[Violation] = []
    ungoverned: list[InputKind] = []

    if table.headings:  # the parse is never asked for when no enabled rule reads it
        match headings_input(database, source):
            case Ungoverned():
                ungoverned.append(InputKind.HEADINGS)
            case HeadingsInput() as subject:
                for rule in table.headings:
                    violations.extend(rule.check(subject))
    ...
    return CheckedSubject(ref, diagnostics=table.located(ref, violations), ungoverned=tuple(ungoverned))
```

- **Adding a rule never touches the runner.** The rule joins its input's partition through the registry
  (NFR-004).
- **Adding an input touches it once**: one branch, one input type, and its query with a carry-over rule. That is
  the deliberate point where a new dependency is reviewed.
- **A rule at `allow` is not in the table**, so it does not run and its input may never be computed (FR-027,
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
  Whether CI can fail on warnings (FR-026) is decided with the file, since the answer may be a prefix set to
  `deny` in it.
- **Resolution order:** the class's default, then a setting by prefix, then a setting by code (FR-024). An
  unknown code, prefix or level is a failure before any subject is checked (FR-025). An alias code resolves to
  its rule's code, with an engine diagnostic at warning on the configuration file naming the code to write. A
  configuration that sets one rule under both its code and an alias code is a failure, so one rule never has two
  settings.
- **A one-run selection filters; it never changes a level** (FR-008). `--select` and `--ignore` take codes or
  prefixes, alias codes resolving with a warning, and narrow which rules run in this run. There is no level option
  on the command line: levels live in the configuration alone, so a local run and CI agree on one revision
  (NFR-001). A selected rule at `allow` stays off, with an engine diagnostic at warning saying the selection does
  not enable it. The established linters' `--select` enables a rule, because they have no levels; with levels,
  enabling a rule is the configuration's, and this is a stated departure.
- **A selection is typed at the boundary.** A selector parses to `RuleCode | RuleGroup`, and an unknown one is a
  failure before any subject is checked (FR-025), never a filter that matches nothing. No filter is the value
  `AllRules`, never an empty set: `select: AllRules | frozenset[RuleSelector]`. The selection reaches the runner
  only as a filter on the rule table, so no rule runs around it.
- **Detection never reads the configuration.** Two rules that overlap are made disjoint in their own logic. The
  name rule compares `name` only when it is a string, so a missing or mistyped `name` belongs to the schema
  rule alone (FR-022).
- **A rule's options are specification data**, read through its input: a line length or a list marker style is
  stated beside the outline and caps, so corpora can differ. The established linters read rule options from
  their settings; this design departs from them because a rule that read the configuration would break the
  invariant above.
- **What a path selects stays in the command line**, where `cli/select.py` chooses subjects today (FR-002 to
  FR-007). The runner receives subjects, sorted by path. The selection bounds what is reported, not what is
  read: a selected skill's link rule still reads the target it links to.
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
| Violation classes and removed rules, the registry, the inputs, the runner, the report types, level resolution | `lorecraft.checks` |
| The configuration file's dialect and its decoding, once it is designed | `lorecraft.project` |
| Path selection, options, text and machine-readable rendering, the exit code, the rule lookup command | `lorecraft.cli` |

No layer is added and the import contract is unchanged.

```text
src/lorecraft/checks/
├── database.py          # gains the decoded text, the cross-file queries and, later, the configuration
├── inputs.py            # the input kinds, and how each is resolved from the queries
├── registry.py
├── runner.py            # replaces run.py's four run functions
├── report.py
└── rules/
    └── <group>/
        ├── __init__.py  # the group: its prefix and title
        ├── <rule>.py    # one rule: its violation class, with its docstring and its check
        └── tests/
```

### Tests

- **A sample rule** is registered over an existing input in a test and runs with no other edit (NFR-004).

### Performance

The engine is efficient within one revision: no query is computed twice, no input is built for a rule that does
not run, and a scan is paid once per subject whatever the number of rules. Caching stays in memory, in the
database, for the revision's lifetime. No result persists across runs in this release (see
[Deferred](#deferred)).

The baseline is v0.2 on this repository, at about 0.85 s per run. Under a profiler, parsing Markdown is 57% of
the run, loading the tokenizer's vocabulary 10% and imports 17%; the checks' own logic does not register. So the
rule count is not today's cost, and the inputs are.

Two measurements keep that true:

- **Before and after**, for NFR-002. The stages are timed apart on this repository: the snapshot, specification
  loading, decoding, parsing, token counting, schema validation, the rules and the rendering. The comparison is
  the median of repeated runs on one machine, with the noise stated. Query counts show that no input is resolved
  twice for a subject.
- **At scale.** A `just` recipe registers a large number of synthetic rules over the existing inputs and times
  the run. The cost per added rule is stated here and stays small and flat: two hundred rules looping over
  twenty headings each, across a hundred subjects, take about 12 ms. A slope that jumps means an input is built
  per rule or a rule scans. It is a recipe run on demand, not a test with a time limit, which a shared machine
  makes flaky.

One cost sits outside the engine and is a change of its own, after this one: the frontmatter query runs the
Markdown parser, so each document is parsed twice. Reading the frontmatter by its fences instead keeps the query
apart from the parse, as early cutoff needs, and must recognise frontmatter exactly as the parser does.

A more elaborate engine waits for a profile that asks for one.

## Alternatives Considered

- **One generic rule type, or a visitor over a syntax tree.** Lorecraft's inputs are small flat values a rule
  iterates on its own. A closed union the runner matches on stays typed and readable.
- **Undecodable and ungoverned as rules.** A rule can be turned off. A file that cannot be read must not be,
  and a missing specification is not a fact about the document.
- **Caching a subject's diagnostics as a query.** Not needed while rules are cheap and a run is one revision.

## Consequences

- **The per-check subcommands go.** One `check` command runs every rule over whatever it is given.
- **Rule documents change in the same change**, since each states something this design makes untrue:
  [module-lorecraft-checks](../code/module-lorecraft-checks.md) (the run, where a rule lives, the shared
  analysis boundary) and [adr-004-database](adr-004-database.md) (decoding as a value, cross-file queries).
- **A projecting rule is thin.** A schema rule is a few lines over a problem type, and the validation it
  projects lives with the input.
- **The runner is hand-written per input kind.** That is the price of typed dispatch with no generic machinery.
- **A later package split.** The established linters keep the database apart from the linter, and
  `lorecraft.checks` holds both. Splitting them adds a layer to the import contract, so it is a change of its own,
  after this one.
- **What stays true:** a check is pure, a judgment is never cached, and every value a rule reads comes from a
  query with a stated carry-over rule.

## Deferred

The PRD defers the IDE-like, long-lived mode. The design builds none of it and closes none of it off.

| Deferred | What the design keeps open |
|---|---|
| Re-checking only what a change affects | A rule declares its input, an input names its queries, and a query states its carry-over rule, so the affected rules are derivable |
| Unsaved content | A rule reads values, never the disk |
| Rejecting a superseded revision's results | One report reads one revision; a diagnostic names no revision-bound object |
| Warm starts | No store is built: caching is in memory, for one revision. Query results stay persistable data, the new queries included, and the registry stays out of them, so the store of [adr-005-incremental](adr-005-incremental.md) is an addition. A cross-file query's carry-over rule names the paths it looked up; recording them waits for the store or for the next revision's carry-over |
| Cached diagnostics | Levels are applied after detection, so a cached result would not depend on the configuration |
| Inline suppression | Its shape is fixed, its syntax Lorecraft's own and modelled on the HTML-comment directives of the Markdown linters, with no compatibility with theirs: `<!-- lorecraft-disable CODE … -->` and `lorecraft-enable` around a block, and `lorecraft-disable-line`, `lorecraft-disable-next-line` and `lorecraft-disable-file`. A directive names its codes, never none, and never a name; an alias code resolves to its rule's code, with a warning. There is no state capture and no in-file configuration: options are specification data and levels are the repository's. The directives are a per-file query, applied after detection where levels are. A directive naming an unknown code, or one that suppressed nothing, is an engine diagnostic, and no engine diagnostic can be suppressed |
| Parallel checking | Output order is sorted, never completion order; the cache is still filled from one thread |

## References

- [prd-008-structured-checks](prd-008-structured-checks.md) - Source: The requirements this design answers
- [#315](https://github.com/LNSD/lorecraft/issues/315) - Source: The research and the decisions behind it
- [adr-009-rules](adr-009-rules.md) - Foundation: The rules the engine runs, and the glossary
- [adr-010-diagnostics](adr-010-diagnostics.md) - Related: What a run reports
- [adr-004-database](adr-004-database.md) - Foundation: Revisions and queries
- [adr-005-incremental](adr-005-incremental.md) - Foundation: Carry-over rules and persistable results
- [adr-006-specifications](adr-006-specifications.md) - Foundation: Governance, computed once by the model
- [module-lorecraft-checks](../code/module-lorecraft-checks.md) - Foundation: The package the engine lives in
