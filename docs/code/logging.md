---
name: "logging"
description: "Structured logging and tracing: module loggers, event fields, nested spans, CLI output layers, and exception records. Load when adding a log event or span, choosing a level, or configuring trace output"
type: "core"
scope: "global"
---

# Logging

**The logger's name is the only handle an operator has on this library.** A logger named for the module it
lives in (`lorecraft_core.checks.frontmatter`) sits inside the package hierarchy, so a single
`logging.getLogger('lorecraft_core').setLevel(logging.DEBUG)` reaches it and everything under it. A logger
named any other way does not, and no amount of correct level choice or message wording repairs that. The
library logs under `lorecraft_core` and the command line under `lorecraft`: two roots, neither inside the
other. Sections 2 through 6 are downstream of section 1.

**Events carry named fields; spans carry duration and parentage.** The library emits them, and the CLI's
opt-in `--trace` configures independent JSON event and span output layers on stderr, on both logger roots.
Errors and their types are owned by
[python-exceptions](python-exceptions.md); what to do with a caught exception beyond logging it is
owned by [python-errors-handling](python-errors-handling.md).

## 1. `logger = logging.getLogger(__name__)`, at Module Level

Every module that logs declares exactly one module-level logger, immediately after its imports, named
`logger`, built from `__name__` and nothing else. Not from `type(self).__name__`, not from a hand-written
string, not stored on an instance.

`__name__` is what places the logger inside the package's own tree. A logger built from a class name is a
**root-level** logger: `getLogger('FrontmatterChecker')` is a sibling of `lorecraft_core`, not a descendant of
it, so `getLogger('lorecraft_core').setLevel(logging.DEBUG)` does not reach it and neither does
`getLogger('lorecraft_core.checks')`. When the base class every checker inherits from does this, every checker's
logger lands outside the hierarchy at once, and the most operationally interesting part of the library becomes
unreachable by hierarchical configuration — the operator can raise the level for `lorecraft_core` and see nothing
change. That is a defect, not a style preference.

A per-instance `self.logger` attribute is a milder problem: `getLogger` returns a process-global singleton per
name, so storing it per instance stores N references to one object. It is redundant rather than broken, and it
goes for symmetry — one way to reach a logger, everywhere.

```python
# ❌ Bad — the logger's name is the class, so it sits outside `lorecraft_core` entirely and no
# `getLogger('lorecraft_core.checks').setLevel(...)` will ever reach it
class CorpusSession:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.logger = logging.getLogger(type(self).__name__)

    def open(self) -> None:
        self.logger.info(f'opened corpus at {self.root}')
```

```python
# ✅ Good — module-level, named for the module, so the whole package tree is configurable
# from one call and every subclass inherits a correctly placed logger
logger = logging.getLogger(__name__)


class CorpusSession:
    def __init__(self, root: Path) -> None:
        self.root = root

    def open(self) -> None:
        logger.info('corpus opened', extra={'fields': {'root': str(self.root)}})
```

## 2. The Level Matches Operational Significance

The level is chosen from what an operator must do about the line, not from how interesting it felt to write.

| Level | For | Examples in this domain |
|---|---|---|
| `error` | A failure someone must act on; results at risk | A document was skipped and never checked, a report was abandoned half-written, a format spec cannot be loaded |
| `warning` | Degraded but self-correcting | A schema fell back to the bundled copy, a spec load was retried, a document was re-read with a relaxed parser |
| `info` | Lifecycle and state changes worth one line in production | Corpus opened, a check run started and finished, a report written |
| `debug` | Diagnostics, off in production | Per-document finding counts, the resolved spec path, the section index built for a document |

The cost of getting this wrong runs both ways and both ways are expensive: routine events at `error` train an
operator to ignore the level that pages them, and a real failure at `debug` is invisible in the one
environment where it mattered.

```python
# ❌ Bad — a routine per-document line at error level, and a skipped document at debug, so the
# pager fires on nothing and the unchecked document is never seen
logger.error(f'checking {document.path}')
logger.debug(f'document {document.path} could not be parsed and was skipped')
```

```python
# ✅ Good — significance, not enthusiasm
logger.debug('document checked', extra={'fields': {'document': str(document.path), 'spec': spec.name}})
logger.error('document skipped', extra={'fields': {'document': str(document.path)}})
```

## 3. Messages Are Brief, Past Tense, and Unpunctuated

A message names what happened, in as few words as carry it, in the past tense, with no trailing period,
exclamation mark, or question mark, and no editorial.

Past tense because the line is written after the fact: "checking corpus" claims work that may never finish,
and when the next line is a traceback the reader has to work out whether it did. No punctuation because it
varies per author and adds a character to every event for nothing.

```python
# ❌ Bad — progressive tense, a sentence, editorial, and a trailing period
logger.info(f'Now beginning the process of checking corpus {corpus_name}...')
logger.info('Successfully finished checking everything!')
```

```python
# ✅ Good — stable event names, with changing values in named fields
logger.info('check started', extra={'fields': {'corpus': corpus_name, 'documents': document_count}})
logger.info('check completed', extra={'fields': {'corpus': corpus_name, 'findings': finding_count}})
```

## 4. `logger.exception` Inside a Handler

Inside an `except` block, a line about the caught exception uses `logger.exception(...)`. It logs at `error`
level and attaches the active traceback, which is the only part of a failure that says where it came from.

`logger.error(f'... {exc}')` records the exception's `str()` and discards the stack, leaving a message that
names a symptom and nothing that locates it. Outside a handler there is no active exception, so
`logger.exception` there logs a bare "NoneType: None" and is a bug.

A handler that logs at a level other than `error` — a retried spec load is a `warning` — uses
`logger.warning(..., exc_info=True)` to keep the traceback at the level it belongs.

```python
# ❌ Bad — the traceback is dropped, so the log says a check failed and nothing about where
try:
    checker.check_document(document)
except CheckerError as exc:
    logger.error(f'check failed: {exc}')
    raise
```

```python
# ✅ Good — the traceback travels with the line
try:
    checker.check_document(document)
except CheckerError:
    logger.exception('check failed', extra={'fields': {'document': str(document.path)}})
    raise
```

```python
# 🔶 Acceptable — a retry is degraded, not failed, so the level drops but the traceback stays
except TransientSpecLoadError:
    logger.warning('spec reload scheduled', exc_info=True, extra={'fields': {'spec': spec_name, 'attempt': attempt}})
```

## 5. Library Code Never Calls `print`

The rule is not "never print". It is that **library code logs, and only an interactive prompt or a function
named for its output writes to stdout.**

A `print` inside library code is unfilterable, unroutable, and invisible to whatever collects the caller's
logs: an embedder who set the level to `warning` still gets it, and an operator grepping the log stream never
does. The carve-outs are named by shape, not by file:

- **A function whose name is its output.** `print_report`, `render_findings_table`, a command body — the
  caller asked for text on stdout and would be astonished to get a log record instead.
- **An interactive prompt that a human must read in real time.** A confirmation before rewriting files has to
  show what is about to change and then block; routing that through a logger means it vanishes for any caller
  who configured logging normally, and the prompt waits on an answer the user never saw it ask for.

Everything else logs.

```python
# ❌ Bad — progress narration on stdout from inside a checker: unfilterable by the embedder,
# invisible to log collection, and interleaved with whatever the caller is printing
def check_corpus(self, documents: Iterable[RuleDocument]) -> list[Finding]:
    findings: list[Finding] = []
    for document in documents:
        print(f'checked {document.path}')
        findings.extend(self.check_document(document))
    return findings
```

```python
# ✅ Good — library progress is a log record at the level it deserves
def check_corpus(self, documents: Iterable[RuleDocument]) -> list[Finding]:
    findings: list[Finding] = []
    for document in documents:
        logger.debug(
            'document checked',
            extra={'fields': {'document': str(document.path), 'spec': self.spec.name}},
        )
        findings.extend(self.check_document(document))
    return findings
```

```python
# 🔶 Acceptable — a human must read this now, in the terminal, for the flow to complete at all
def confirm_rewrite(path: Path, finding_count: int) -> bool:
    """Ask for approval to rewrite a document, blocking until the user answers."""
    print(f'{path} has {finding_count} findings that can be fixed in place')
    return input('rewrite it? [y/N] ').strip().lower() == 'y'
```

## 6. Library Code Never Calls `basicConfig`

`logging.basicConfig`, `logger.addHandler`, `logging.getLogger().setLevel`, and every other call that
configures the logging system belong to the **application**, never to a library module. A library emits
records; the process that imported it decides where they go.

`basicConfig` attaches a handler to the **root** logger, process-wide. Calling it on import means importing
this library silently reconfigures the host application's logging — its format, its destination, sometimes its
level — and the host's own careful configuration loses or duplicates depending on import order. The failure
shows up as duplicated lines or a mysteriously changed format in an application that never asked, and it is
diagnosed only by someone who thinks to suspect an import.

The one legitimate defensive call is `logging.getLogger('lorecraft_core').addHandler(logging.NullHandler())` at
the package root, which suppresses the "no handlers could be found" warning without configuring anything.
Entry points — a command-line `main`, a one-off script, a test fixture — configure freely; they are the
application.

```python
# ❌ Bad — in a library module, this reconfigures the root logger of whatever process imports it
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

logger = logging.getLogger(__name__)
```

```python
# ✅ Good — the library declares a logger and nothing else; the entry point configures
logger = logging.getLogger(__name__)
```

## 7. Keep Event Names Stable and Put Values in Fields

New log calls use a brief, stable message for the event and put variable values in `extra={'fields': {...}}`.
The CLI JSON formatter preserves these fields and attaches the active trace and span IDs. Stable messages can
be grouped across documents; named fields can be filtered without parsing prose. Keep field values JSON
serializable so the stderr formatter can encode every event. Existing interpolated messages can be migrated
when their call sites change.

```python
# ✅ Good — the event name stays stable and document details remain queryable
logger.debug('document checked', extra={'fields': {'document': path, 'findings': count}})
```

## 8. Nest Spans Around Operations With Meaningful Duration

Use OpenTelemetry spans for a check run and its per-document work. Give spans stable operation names and add
small scalar attributes such as the document path and finding count. A nested span gives the work a parent,
duration, and trace identity without coupling library code to an exporter. The application owns span export
and log handlers, so an importing process remains free to configure its own output layers.

```python
# ✅ Good — the child span records duration and links its event to the parent run
with tracer.start_as_current_span('check.header.document') as span:
    span.set_attribute('document.path', path)
    logger.debug('document checked', extra={'fields': {'document': path}})
```

## Checklist

Before committing code, verify:

- [ ] Every module that logs has exactly one `logger = logging.getLogger(__name__)` after its imports
- [ ] No logger is built from `type(self).__name__`, a class name, or a literal string
- [ ] No logger is stored as `self.logger` or any other instance or class attribute
- [ ] Each new log call's level matches the table in [§2](#2-the-level-matches-operational-significance) — no
      routine event at `error`, no failure at `debug`
- [ ] Every message is past tense, has no trailing punctuation, and carries no editorial
- [ ] Every log call inside an `except` block uses `logger.exception(...)`, or a lower level with
      `exc_info=True`
- [ ] No `logger.exception` call sits outside an `except` block
- [ ] No `print` in library code, except a function named for its output or a prompt a human must read live
- [ ] No `basicConfig`, `addHandler`, or root-logger `setLevel` outside an entry point — `NullHandler` at the
      package root excepted
- [ ] No log call sits in a per-line loop, whatever its level
- [ ] New events use stable messages and JSON-serializable values under `extra={'fields': {...}}`
- [ ] Operation spans have stable names, scalar attributes, and a parent where the operation is nested
- [ ] Library modules do not configure a tracer provider, exporter, or log handler

## References

- [python-errors-handling](python-errors-handling.md) - Related: Owns what an `except` block does beyond logging — retry, re-raise, or swallow
- [python-exceptions](python-exceptions.md) - Related: Owns the exception types whose messages end up in these lines
- [python-modules](python-modules.md) - Related: Owns the module boundary that `__name__` names, and the package root where `NullHandler` is attached
- [principle-least-surprise](principle-least-surprise.md) - Foundation: A library that reconfigures the host's logging on import surprises the host
- [principle-information-hiding](principle-information-hiding.md) - Foundation: A library exposes records; where they go is the application's decision

## External References

- [Python docs — Logging HOWTO: Configuring Logging for a Library](https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library)
- [Python docs — `logging.Logger.exception`](https://docs.python.org/3/library/logging.html#logging.Logger.exception)
- [Python docs — Logging Cookbook](https://docs.python.org/3/howto/logging-cookbook.html)
- [OpenTelemetry Python — Instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/)
- [Rust tracing — spans, events, and subscribers](https://docs.rs/tracing/latest/tracing/)
