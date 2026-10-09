---
name: "adr-010-diagnostics"
description: "What a rule of the structured checks reports and how it reaches the user: a diagnostic with labelled locations, help and notes rendered from the context the check captured, two severities, one report per subject in one shape, a total output order, and exit codes. Load when changing what a rule reports, adding a label, a help or a note, or changing the text output, the machine-readable output, the order or the exit codes"
type: "adr"
status: "accepted"
---

# Diagnostics: What a Rule Reports

> [!NOTE]
> Supersedes [adr-007-findings](adr-007-findings.md): its identifiers, notes, report types, order, output and exit
> codes. What adr-007 states that still holds is restated here, and adr-007 binds no code.

This record is one of three that state how the structured checks of [prd-008](prd-008-structured-checks.md) are
built: [adr-009](adr-009-rules.md) how a rule is declared and identified, [adr-010](adr-010-diagnostics.md) what a
rule reports and how it reaches the user, and [adr-011](adr-011-rules-engine.md) how a run judges subjects.
Requirement identifiers such as `FR-009` cite the PRD, and the terms are those of [adr-009's
glossary](adr-009-rules.md#glossary). Names of types, modules, codes and prefixes in the sketches are illustrative;
the shapes are the decision.

## Context

Before this record, a check returned violations whose message is free text, with notes built as strings inside the
check. The run located them into findings, collected them per check into a report type per subject kind, and
ordered them as the paths were given and the checks happened to state them. A document no meta spec governs
printed in the shape of a rule. [adr-007-findings](adr-007-findings.md) stated that contract, and Lorecraft v0.2
shipped it.

What a user needs from a diagnostic is what the established compilers and linters give: what is wrong, where,
why, and how to fix this occurrence, with the related places in other files pointed at, in an order that does
not change between two runs over the same revision.

## Decision

1. **A diagnostic is as rich as the established compilers' and linters'**: a message, a labelled primary
   location, labelled secondary locations in any file, and help and notes that may each point somewhere. The
   check captures the context it saw as typed data on the occurrence, and the occurrence renders every part from
   that data.
2. **One report per subject**, and one diagnostic shape for every subject kind. A diagnostic holds its occurrence.
3. **The order is a contract**, total over one revision: path, location, severity, code, message.
4. **Only a rule's occurrence is a rule diagnostic.** A file that cannot be decoded is an engine diagnostic, a
   subject no meta spec governs is coverage, and what stops a run is a failure: none of them takes a level.
5. **Only the command line prints.** A rule returns its occurrences as values, the run locates them into
   diagnostics, and the command line alone renders them and chooses the exit code. A problem in a subject is a
   diagnostic and the run goes on; only what stops Lorecraft from judging at all is raised.

## Design

### Diagnostics a Rule Renders

A diagnostic tells the writer what is wrong, where, why, and how to fix this occurrence, at the level of the
established compilers' and linters' diagnostics:

```text
error[OUT006]: missing required section `Usage`
  --> docs/feat/cli-check.md:12
   │
12 │ ## Options
   │ ────────── expected `Usage` before `Options`
   │
  ::: docs/__meta__/feat.structure.json
   │
   = note: the document structure is set here
   = help: describe how to invoke the command
   = note: for example:
           ## Usage
           ...
```

What goes into it depends on the context of the occurrence, and only the check sees that context. So the check
captures what is relevant as typed fields of the occurrence, and methods of the occurrence render each part of the
diagnostic from those fields:

```python
@rule
@dataclass(frozen=True, slots=True, kw_only=True)
class MissingSection(DocumentRule):
    """..."""

    CODE: ClassVar[RuleCode] = RuleCode(GROUP_ID, 6)
    ...
    spec: RootRelativePath
    section: SectionName
    before: str | None                # the heading it should precede; None at the end, reported at the last line
    description: str | None           # the meta spec's guidance, through the context
    example: str | None

    def message(self) -> str:
        return f'missing required section `{self.section}`'

    def labels(self) -> tuple[Label, ...]:
        if self.before is None:
            return (Label(Here(self.line), f'expected `{self.section}` before the end of the document'),)
        return (Label(Here(self.line), f'expected `{self.section}` before `{self.before}`'),)

    def children(self) -> tuple[Subdiagnostic, ...]:
        parts: list[Subdiagnostic] = [spec_note(self.spec)]  # Note('the document structure is set here', at=...)
        if self.description is not None:
            parts.append(Help(self.description))
        if self.example is not None:
            parts.append(Note(f'for example:\n## {self.section}\n\n{self.example}'))
        return tuple(parts)
```

```python
@dataclass(frozen=True, slots=True)
class Here:                    # a line in the subject; the runner supplies its path
    line: int


@dataclass(frozen=True, slots=True)
class WholeSubject:            # a subject without lines, such as a layout entry
    pass


@dataclass(frozen=True, slots=True)
class Elsewhere:               # another file: the meta spec, a link's target, a first definition
    path: RootRelativePath
    line: int | None = None


type Primary = Here | WholeSubject
type Location = Here | Elsewhere


# For a subject with lines: a label or a sub-diagnostic may point at one of its lines, or elsewhere.
@dataclass(frozen=True, slots=True)
class Label:
    at: Location
    text: str


@dataclass(frozen=True, slots=True)
class Help:
    text: str
    at: Location | None = None


@dataclass(frozen=True, slots=True)
class Note:
    text: str
    at: Location | None = None


type Subdiagnostic = Help | Note


# For a layout entry, which has no lines: a label or a sub-diagnostic can only point elsewhere.
@dataclass(frozen=True, slots=True)
class EntryLabel:
    at: Elsewhere
    text: str


@dataclass(frozen=True, slots=True)
class EntryHelp:
    text: str
    at: Elsewhere | None = None


@dataclass(frozen=True, slots=True)
class EntryNote:
    text: str
    at: Elsewhere | None = None


type EntrySubdiagnostic = EntryHelp | EntryNote
```

```python
class Rule:
    def primary(self) -> Primary: ...                                      # abstract
    def labels(self) -> tuple[Label | EntryLabel, ...]: ...
    def children(self) -> tuple[Subdiagnostic | EntrySubdiagnostic, ...]: ...


class ContentRule(Rule):        # the base of every rule base whose subject has lines
    line: int

    def primary(self) -> Here:
        return Here(self.line)

    def labels(self) -> tuple[Label, ...]:
        return ()

    def children(self) -> tuple[Subdiagnostic, ...]:
        return ()


class LayoutRule(Rule):         # the base of the rule base over a layout entry
    def primary(self) -> WholeSubject:
        return WholeSubject()

    def labels(self) -> tuple[EntryLabel, ...]:
        return ()

    def children(self) -> tuple[EntrySubdiagnostic, ...]:
        return ()
```

- **`message()` names the condition** and never branches: a different condition is a different rule. It is
  the one method every rule writes.
- **`labels()` and `children()` adapt to the context.** A label or a help may depend on what the check
  captured, such as the heading a missing section should precede, or the first definition a duplicate key
  repeats. The base returns none of either, so a rule that needs only a message writes nothing more, and its
  primary location is unlabelled.
- **Each subject kind gets only the locations it has, and the type checker holds it.** A layout rule's occurrence
  has no `line` field, so one cannot be built with a line, and a content rule's occurrence cannot be built without
  one. Each base narrows `labels()` and `children()` to its own types, as a method override may narrow its return
  type and a tuple is covariant, so a layout rule cannot write `Here`. The renderer matches `primary()` on
  `Here | WholeSubject` with `assert_never`, and never reads a line by `getattr`. The label and sub-diagnostic
  types are separate classes per subject kind, not subclasses that narrow a field, which a type checker may not
  accept. No type proves that `Here(12)` is a line the file has: that is a runtime value, and each rule's tests
  hold it.
- **Context is data, never prose built in `check`.** An occurrence stores what the check saw, and the methods turn
  it into text. A persisted or machine-read diagnostic keeps the structured values, and the text can always be
  rendered again from them.
- **The meta spec authors its own guidance.** An outline entry's description and example reach the
  occurrence through the context, and `children()` presents them; the rule writes no guidance a meta spec
  states.
- **An occurrence still names no subject.** `Here` is a line of the subject, and `WholeSubject` the subject itself;
  the runner adds the path. `Elsewhere` names another file. Ranged locations, when they come, widen `Here` and
  `Elsewhere` without changing a rule's signature.
- **The docstring's *Use instead* is the general fix**, on the rulebook page; `children()` gives the fix for
  this occurrence, printed with the diagnostic.
- **Engine diagnostics take the same shape**: an undecodable file can label where its first invalid byte is.
- **How the parts are laid out is the command line's.** The text takes the established compilers' layout: an
  arrow to the primary location, the source lines in a numbered gutter, an underline beneath the labelled line, a
  `:::` pointer to each other file, and help and notes as `=` lines. It draws with Unicode box-drawing characters:
  the gutter is one connected `│` line, the primary label's underline a thin `─` line, and a secondary label's in
  the same file a dotted `┄` line. Where the output cannot carry Unicode, such as a stream whose encoding is not
  UTF-8, the gutter falls back to `|`, the primary underline to `^` and the secondary one to `-`. It renders the
  source lines from the same revision's text query. The machine-readable output carries the code, the rule's name,
  the severity, the message, the labels and the children as structured entries. A language-server client receives
  the primary label on the diagnostic's range, and the secondary labels and located notes as related information.
- **Three output formats, one order.** `check --format` takes `text`, the layout above for a person; `short`, one
  line per diagnostic, `path:line: severity[CODE]: message`, for an editor or `grep` to match; and `json`, one
  compact UTF-8 document for a script. All three print the diagnostics in the order below. Only `text` is coloured,
  as `--color` chooses: `auto` colours a terminal unless `NO_COLOR` is set, and `FORCE_COLOR` forces it. With
  `text` and `short`, the diagnostics go to stdout and the coverage and the summary to stderr, so a pipe reads the
  diagnostics alone. [cli-check](../feat/cli-check.md) documents each format.

### Diagnostics and the Report

```python
@dataclass(frozen=True, slots=True)
class RuleDiagnostic:
    path: RootRelativePath
    occurrence: Rule
    severity: Severity  # ERROR or WARNING, from the rule's level


@dataclass(frozen=True, slots=True)
class EngineDiagnostic:
    path: RootRelativePath
    occurrence: EngineCondition

    @property
    def severity(self) -> Severity:
        return self.occurrence.SEVERITY  # fixed by the condition's class


type Diagnostic = RuleDiagnostic | EngineDiagnostic
type SubjectReport = CheckedSubject | UndecodableSubject | CheckedLayoutEntry
```

- **A diagnostic holds its occurrence** and copies none of its fields. The code, the message, the labels, the
  help and notes, and the meta spec reach the text and the machine-readable output through it (FR-017).
- **An engine diagnostic's severity cannot be set.** It is read from the condition's class, so an engine
  condition reported at a severity its class does not fix cannot be built. Renderers and the order take the one
  name `Diagnostic`, and read the same attributes on both kinds.
- **`Severity` is not `Level`.** A level has three values, and a diagnostic at `allow` does not exist, so a
  diagnostic carries one of two severities.
- **An undecodable subject has no diagnostics and no coverage**, which the union states.
- **A layout entry is reported by its path, and has no coverage.** It is not a document, a skill or a resource, so
  it has no subject reference, and no meta spec governs it, so it can never be ungoverned. Its diagnostics take the
  same shape as every other subject's.
- **Order is a documented output contract** (FR-018), the established linters' source order grouped by file:
  1. the subject's root-relative POSIX path, compared by code point, never by locale and never by how the paths
     were typed;
  2. the primary location, `WholeSubject` first, then the line, and the column once locations are ranged;
  3. the severity, an error before a warning;
  4. the code, as printed, whose fixed-width digits make that numeric order within a group;
  5. the message text, so the order never depends on how a rule iterates.

  The order is total, so one revision always prints the same output (NFR-001). It is one sort key, which matches
  `primary()` with `assert_never`, so a new kind of location cannot exist without a place in the order. Changing
  the order is a breaking change, carried in the release notes like any output change.
- **The run's result** is the subject reports. The summary and the coverage are derived from them. The text is
  presented per file (FR-016), and the machine-readable output is one document holding the diagnostics, the
  summary and the coverage (FR-021).
- **Exit codes** are 0 for a clean run, warnings included, 1 for any error diagnostic or undecodable file, and 2
  for a failure or invalid input. A failure, such as a meta spec that cannot be loaded or a file missing from the
  snapshot, is outside every level and selection. Most are raised before any subject is checked, and one raised
  during the run discards what the run found: the command line prints the failure alone, never a partial report.
  Invalid input, such as an unknown selector or a usage error, also exits 2, before the run starts.

### Tests

- **The command line:** the text through snapshots, the machine-readable output through whole-document
  assertions.
- **Per rule:** a case that triggers it asserts the labels and sub-diagnostics it renders, and their lines, since
  no type proves that a `Here` names a line the file has.

## Alternatives Considered

- **Notes as a field of the occurrence**, built as text in `check`, as the checks do today. Not chosen: a rule's
  fixed help repeats in every instance, a stored diagnostic holds rendered prose instead of data, and nothing ties
  a rule to the guidance it gives.
- **Emission order**, as compilers print. Not chosen: the order would depend on how rules iterate, and two runs
  over one revision could differ.
- **Rule-first order**, all of one rule before the next. Not chosen: a reader works through a file top to bottom,
  and the source order keeps a file's diagnostics together in that order.

## Consequences

- **The output breaks.** The machine-readable output becomes one document, every diagnostic carries a code and a
  severity, and the order changes. The release notes carry the migration.
- **Names change in the code.** `Finding` becomes `Diagnostic`, and the parallel report and run types collapse
  into `SubjectReport`.
- **[adr-007-findings](adr-007-findings.md) is superseded**: its dotted identifiers, now codes; its notes, now
  labels and sub-diagnostics a rule renders; its run per check, now one report per subject; its order; its exit
  code 1 for any finding, now for an error only; and its own name, since a finding is now a diagnostic. Its
  violations as values, its findings apart from failures and its command line as the only printer carry over as
  Decisions 4 and 5. It stays the record of what Lorecraft v0.2 reports.

## Deferred

| Deferred | What the design keeps open |
|---|---|
| Ranged locations | `Here` and `Elsewhere` widen from a line to a range, and no rule's signature names either |
| Fixes | `Help` gains an optional edit with its applicability: whether a tool may apply it unattended |

## Checklist

Before committing code, verify:

- [ ] A rule's `message()` names the condition and never branches; context reaches the diagnostic through typed
  fields and `labels()` and `children()`, never as prose built in `check`
- [ ] Guidance a meta spec states reaches `children()` through the context, and the rule does not restate it
- [ ] A layout rule's labels and sub-diagnostics are the `Entry*` types, and no location is read by `getattr`
- [ ] A diagnostic holds its occurrence and copies none of its fields; an engine diagnostic's severity is its
  condition's
- [ ] Every output format prints the diagnostics in the one total order: path, primary location, severity, code,
  message
- [ ] A problem in a subject is a diagnostic or coverage, never a raised error; only what stops the run is raised
- [ ] Nothing below the command line prints, and only `text` output is coloured
- [ ] The exit code is 0 with no error diagnostic, 1 with any, and 2 for a failure or invalid input, after which
  only the failure is printed
- [ ] A change to a JSON key, the short line or the order is a breaking change, carried in the release notes
- [ ] A rule's tests assert the labels and sub-diagnostics it renders, and their lines

## References

- [prd-008-structured-checks](prd-008-structured-checks.md) - Source: The requirements this design answers
- [#315](https://github.com/LNSD/lorecraft/issues/315) - Source: The research and the decisions behind it
- [adr-009-rules](adr-009-rules.md) - Foundation: The rule class that renders a diagnostic, and the glossary
- [adr-011-rules-engine](adr-011-rules-engine.md) - Related: The run that locates occurrences into diagnostics
- [adr-001-snapshot-model](adr-001-snapshot-model.md) - Related: The model and the package roles
- [adr-006-specifications](adr-006-specifications.md) - Related: Where the rules a diagnostic cites come from
- [adr-007-findings](adr-007-findings.md) - Supersedes: Violations, findings and failures
- [cli-check](../feat/cli-check.md) - Leads to: The output formats as shipped
- [error-boundaries](../code/error-boundaries.md) - Foundation: Where a failure is raised and where it is reported
