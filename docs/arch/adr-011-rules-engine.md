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

1. **A rule reads its subject through its kind's context** and declares the facet it is governed for; the
   frontmatter, outline and other length rules still read one of a closed set of inputs until they move. A rule
   never scans: every pass over text, a tree or a schema is a query, and a rule only loops over the values its
   context or input hands it. An analysis several rules share is a query of the database, never a rule with several
   codes.
2. **One runner** resolves each input once per subject, only when an enabled rule reads it, with one
   hand-written branch per input kind, and one per subject kind for the rules that read a context.
3. **A subject's status is the engine's, not a rule's.** Whether a file decodes, and whether a specification
   governs each facet (each input, for a rule still on one), is resolved before any rule runs.
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
                     · partitioned by subject kind or input kind, in code order
                     · any failure (unknown code, bad config) is raised here, before any subject
                       │
                       ▼
                   runner(database, subjects, table)
                     for each subject:
                       decode → witness, or an undecodable engine diagnostic
                       for each input kind with enabled rules:
                         build the input once from the queries → governed or ungoverned
                         for each rule in that partition: rule.check(input) → occurrences
                       locate the occurrences into diagnostics with the table's severities
                       │
                       ▼
                   subject reports → command line renders text / JSON, exit code
```

- **Generic over rules.** The runner never names a rule: a new rule is a class the registry collects, and it
  joins its input's partition of the table.
- **Specific over inputs.** The runner has one hand-written branch per input kind, which keeps dispatch typed:
  the headings partition holds `type[HeadingsRule]`, so `rule.check(input)` checks against `HeadingsInput`.
- **Configuration and selection never reach a rule.** They shape the table and nothing else.
- **Subjects arrive chosen.** The command line resolves the paths into subjects; the runner receives a document's
  ref or a skill's location as the model issued it, or a resource's location as its skill's resource listing issued
  it, the database and the table, and nothing else.

### Inputs

An input is a frozen value of Lorecraft's own types: the facts a query returned, the specifications that govern
them, and the subject's identity values, such as a filename or the directory a skill is listed under. For the
rules not yet moved onto a context, a rule receives one input and nothing else: never the database, a view or a
path.

The set is closed. Each kind is one dataclass and one rule base class whose `check` takes it.

| Input | Subjects | Built from | Governed by |
|---|---|---|---|
| Frontmatter block | document, skill | the frontmatter query | a frontmatter schema; for a skill, the package, after the Agent Skills specification |
| Schema problems | document, skill | the schema-problems query, a skill's against the Agent Skills specification | a frontmatter schema |
| Headings | document | the parse query | a structure specification |
| Outline divergence | document | the outline-divergences query, over the parse and line-count queries | a structure specification that states an outline |
| Layout | layout entry, skill | the model, the skill's resource listing | the package |

Three rules follow from the table.

**An input scans, a rule loops.** Building an input is where the cost of a run lies: the parse, and the shared
analyses the input reads from their queries. A rule's own work is a loop over a short tuple the input prepared. So a
scan written inside a rule is paid once per rule, and the same scan written as an input is paid once per subject,
however many rules read it. A rule never walks text or a tree: the scan it needs is an input, existing or new. A rule
that needs two facts, such as the headings and the frontmatter, gets one input that holds both, never two
inputs. A new input is the runner's one reviewed extension point, so it is where a new cost enters and is
reviewed.

**A shared analysis is a query.** Schema validation and outline matching each find several conditions in one
pass. Each is a pure function of the revision's per-file queries and the specifications that govern the subject, so
it is memoized on the database like any other query, with its own carry-over rule: `schema_problems` and
`skill_schema_problems` are kept whenever the frontmatter is and, for a document, the model is, and
`outline_divergences` whenever the parse and the line count are and the model is. The runner asks for it once per
subject, as a tuple of typed problems, and only when an enabled rule reads it and a specification governs the subject
for it, so an ungoverned subject never pays for it. Each condition is then a rule that projects its own problem type
into its occurrences. The analysis finds problems, never diagnostics: levels are applied after detection, so no
diagnostic is cached and a rule's result still is not.

**A cross-file input is a query.** The link-target states are a query keyed by the subject's ref, one per kind of
Markdown file, read through `link_targets()`: what the snapshot holds at the target of each relative link, present,
missing or outside the scope the scan read, keyed by the link's normalised relative path. Each link is read from the
file's `link_base()`, the skill root for any file of a skill and the document's own directory for a document, and a
link climbing past that bound has no entry. The query states facts; whether a missing target makes a link broken is
the rule's. Its carry-over rule names every path it looked up, an absent target included, since creating a missing
target must remove its diagnostic. Nothing a rule reads is left outside a query contract.

**A subject's facts are also stated as a context.** `lorecraft.project` declares, as a `Protocol` per subject kind,
what can be asked of one decoded subject: `DocumentContext`, `SkillContext` and `SkillResourceContext`. The first
two extend `FrontmatterContext`, and all three extend `MarkdownContext`, what any one Markdown file has, starting
with its parse tree; a skill's Markdown file is its `SKILL.md` alone. The last two also extend `SkillFileContext`,
what one of a skill's files has, since every file of a skill names another from the skill root.
`lorecraft.project.database` implements them over the database, bound to the decode witness: each fact one memoized
query, each identity value read from the subject's ref or location. A document context is built only for a document
whose corpus states a structure specification, since no facet governs one whose corpus does not.

**A rule may read its subject's context.** `lorecraft.rules` gives each subject kind a rule base whose `check` takes
the context: `DocumentRule` over a document, `SkillRule` over a skill, `MarkdownRule` over any one Markdown file,
and `SkillFileRule` over one of a skill's files, its `SKILL.md` or a resource, never a document. A rule over a
document declares the facet it reads in `GOVERNED_BY`, one of `Facet.FRONTMATTER` (a frontmatter schema governs it),
`STRUCTURE` (its corpus states a structure specification), `OUTLINE` (a specification states an outline) and
`BUDGET` (a specification sets a token budget). A rule over a Markdown file declares none: it judges a document
governed for `STRUCTURE`, the facet under which a document has a context at all, and every skill's `SKILL.md` and
every resource, which the package governs; a rule over a skill's file declares none either. The token budget,
`LEN001`, is a document rule governed by `BUDGET`, and the line budget, `LEN002`, a skill rule, so the token and line
counts are no longer inputs; the links rules read a context too, `LINK001`, `LINK002` and `LINK003` deriving from
`MarkdownRule` and `LINK004` from `SkillFileRule`. The other rules still read the inputs above until they move onto a
context. A `FrontmatterRule` base over a `FrontmatterContext`, for a rule that reads a document's or a skill's
frontmatter alike, arrives with the frontmatter rules.

### A Subject's Status Comes Before Any Rule

- **Readable or undecodable.** A file is decoded once, as a query value: its text, or an undecodable marker,
  cached like any result. The runner decodes every selected subject, whatever the levels. That is the one read
  NFR-003 does not gate, so that FR-020 holds under any configuration.
- **Governed or ungoverned, per facet.** Governance comes from the model, which computes it once. A document can be
  governed for its frontmatter and ungoverned for its outline. The runner runs a rule over a document only when the
  document is governed for the rule's facet, and records each facet an enabled rule reads that it is not governed
  for; a rule still on an input records that input kind instead. A skill and a resource are governed by the
  package for every facet, so neither is ever ungoverned.
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
registry and the resolved levels: the enabled rules, partitioned by subject kind, or by input kind for a rule still on
an input, in code order. Each partition holds every enabled rule beside its severity, so a rule the runner holds
always has one. For a document, the runner builds one context, then for each facet an enabled document rule
declares, runs those rules over the context or records the facet as ungoverned; the Markdown rules run beside the
`STRUCTURE` rules. For a skill, it builds one context and runs every skill rule, every Markdown rule and every
skill-file rule over it. For a resource, it builds one context and runs every Markdown rule and every skill-file rule
over it. The input branches below stay beside these until the last rule reads a context.

```python
def _check_document(database: Database, ref: DocumentRef, table: RuleTable) -> SubjectReport:
    source = database.text(ref)
    if isinstance(source, Undecodable):
        return UndecodableSubject(ref)
    # `source` is a `DocumentText` from here on: the witness every per-file query takes

    diagnostics: list[Diagnostic] = []
    ungoverned: list[InputKind] = []

    if table.headings_rules:  # the parse is never asked for when no enabled rule reads it
        match build_headings_input(database, source):
            case Ungoverned():
                ungoverned.append(InputKind.HEADINGS)
            case HeadingsInput() as subject:
                for enabled in table.headings_rules:
                    for occurrence in enabled.rule.check(subject):
                        diagnostics.append(RuleDiagnostic(ref.path, occurrence, enabled.severity))
    ...
    return CheckedSubject(ref, diagnostics=tuple(diagnostics), ungoverned=tuple(ungoverned))
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
| Rule classes and removed rules, the registry, the rule groups and their rules, the rule bases per subject kind and the facets, the input types | `lorecraft.rules` |
| Building the inputs, the runner, the report types, level resolution | `lorecraft.checks` |
| The context protocols, what can be asked of one decoded subject | `lorecraft.project` |
| The database, decoding, the contexts' implementations ([adr-012](adr-012-database-derivation.md)) | `lorecraft.project.database` |
| The configuration file's dialect and its decoding, once it is designed | `lorecraft.project` |
| Path selection, options, text and machine-readable rendering, the exit code, the rule lookup command | `lorecraft.cli` |

`lorecraft.rules` is a layer of its own, below `lorecraft.checks` and above `lorecraft.project`. A forbidden contract
refuses a rule that imports `lorecraft.project.database`, so a rule cannot reach the database by import, which the
design could otherwise only state.

```text
src/lorecraft/rules/
├── inputs.py            # the input kinds the rules not yet on a context read
├── subject.py           # the rule base per subject kind, and the facets
├── registry.py
└── <group>/
    ├── __ruleset__.py   # the group: its prefix and title, and what its rules share
    ├── <rule>.py        # one rule: its class, with its docstring and its check
    └── tests/

src/lorecraft/project/database/
├── context.py           # the database-backed contexts; their protocols are in project/context.py
├── database.py          # gains the decoded text, the cross-file queries and, later, the configuration
└── text.py              # the decode witnesses

src/lorecraft/checks/
├── inputs.py            # how each input kind is resolved from the queries
├── runner.py            # replaces run.py's four run functions
└── report.py
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
  [module-lorecraft-checks](../code/module-lorecraft-checks.md) (the run and the shared
  analysis boundary) and [adr-004-database](adr-004-database.md) (decoding as a value, cross-file queries).
- **A projecting rule is thin.** A schema rule is a few lines over a problem type, and the validation it
  projects lives in a query.
- **The runner is hand-written per input kind.** That is the price of typed dispatch with no generic machinery.
- **The database sits apart from the linter**, as the established linters keep it. The rules sit in
  `lorecraft.rules`, the runner in `lorecraft.checks`, and the database, with its witnesses and the contexts'
  implementations, in `lorecraft.project.database`, beside the derivations it memoizes
  ([adr-012](adr-012-database-derivation.md)). The split adds no layer to the import contract.
- **What stays true:** a check is pure, a rule's result is never cached, and every value a rule reads comes from a
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
- [adr-012-database-derivation](adr-012-database-derivation.md) - Foundation: The database in the Derivation package
- [module-lorecraft-checks](../code/module-lorecraft-checks.md) - Foundation: The package the engine lives in
