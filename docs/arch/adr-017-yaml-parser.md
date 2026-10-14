---
name: "adr-017-yaml-parser"
description: "Frontmatter is parsed with a pure-Python YAML parser, ruamel.yaml's event API in place of PyYAML's, reading the format adr-019 defines, so no runtime dependency carries a C extension. Load when changing how frontmatter is parsed, touching src/lorecraft/project/syntax/frontmatter.py or anything under src/lorecraft/yaml/, or adding or upgrading a YAML dependency"
type: "adr"
status: "accepted"
---

# A Pure-Python YAML Parser for Frontmatter

## Context

What frontmatter may hold is plain frontmatter, a subset of YAML 1.2 that [adr-019](adr-019-frontmatter-format.md)
defines and refuses the rest of from the tokens and events lorecraft reads. This record decides only the parser that
produces those tokens and events.

`src/lorecraft/project/syntax/frontmatter.py` drove PyYAML's (`pyyaml>=6.0,<7`) low-level reader, scanner and parser
and built the value from the event stream itself; it never called `yaml.safe_load`. `FM002 invalid-yaml` reports a
syntax error on the line the parser names.

That path is PyYAML's pure-Python code, so the libyaml C extension is never used. It still ships: PyYAML is
published as platform wheels with the compiled `_yaml` module, plus an sdist. A new CPython release or a
free-threaded build has to wait for PyYAML's wheels for it, or build the extension from source, so the dependency
held lorecraft's upgrades back for code lorecraft does not run.

The candidates were compared on lorecraft's own corpus: every `*.md` under `docs/`, `skills/` and
`.claude/skills/` at `9e1d8b7`, 147 frontmatter blocks of 597 lines, on CPython 3.13. Parse time is the median of
30 passes; import cost is measured with hyperfine against a bare interpreter start.

| | PyYAML 6.0.3, pure path | ruamel.yaml 0.19.1, pure | strictyaml 1.7.3 | Hand-written subset parser |
|---|---|---|---|---|
| Events with line marks | Yes | Yes; identical to PyYAML's on every corpus block | No; document API only | If written |
| `FM002` line | Baseline | Same on every syntax-error probe | Crashes on a control character | Must be re-proved |
| Parse time, corpus | 25.8 ms | 33.7 ms (1.3×) | 111.3 ms (4.3×) | Not measured |
| Import cost | +9.3 ms | +10.8 ms | +19.4 ms | ≈0 |
| Distribution | Platform wheels with a C extension | One `py3-none-any` wheel; `clib` is an optional extra | Three packages, vendors ruamel.yaml 0.16 | None |

A full `lorecraft check` of this repository takes about 855 ms, so YAML parsing is a few percent of a run under
every option.

## Decision

1. **ruamel.yaml's pure-Python event API is the parser**, in `lorecraft.yaml` behind `read_yaml`, with its reader,
   scanner and parser subclasses in `src/lorecraft/yaml/basic_yaml.py`. `read_yaml`, in `src/lorecraft/yaml/reader.py`,
   reads ruamel.yaml's tokens and events, with their start marks: the value is built from the events by lorecraft,
   never by a ruamel.yaml loader or constructor, and is a tree of `lorecraft.yaml` values, or the first `YamlProblem`
   the block writes. `frontmatter.py` maps that tree onto frontmatter.
2. **The parser reads the format adr-019 defines, and does not define it.** What is accepted, what is refused and how
   a refusal is worded are adr-019's; this record adds no rule about the format.
3. **Every problem the parser meets in a block is `FM002`, never a crash.** `read_yaml` returns it as a `YamlProblem`,
   and a syntax error's texts and positions, a `SyntaxErrorProblem`, are handed to adr-019's classification, which
   words it; the parser's text is never shown. No ruamel.yaml type leaves `lorecraft.yaml`. Where
   its scanner lets a plain `ValueError` escape, a `\U` escape above `U+10FFFF` or a directive version number too
   long to convert, it is raised as a scanner error on its line first.
4. **`ruamel.yaml` is a runtime dependency, pinned `>=0.19,<0.20`**, and its C extension is never installed:
   `ruamel.yaml.clib` is not a dependency of lorecraft, and the `clib` extra is not requested.
5. **`pyyaml` is not a dependency of lorecraft**, at runtime or in development: `pyproject.toml` declares it in no
   dependency group or extra, and no module under `src/` or `tests/` imports `yaml`.
6. **Parity with PyYAML is checked once**, on the change that switches parsers, and its result is recorded on that
   pull request. No committed test compares with PyYAML: from then on, adr-019's tests hold what frontmatter reads as.

## Alternatives Considered

- **Keep PyYAML.** The fastest of the pure-Python options and the cheapest to import, with no code to change. Not
  chosen: it keeps the C extension in every install and its platform wheels on lorecraft's upgrade path, which is
  the cost this decision removes.
- **strictyaml.** Its own API refuses anchors, aliases and tags. Not chosen: it gives no event access, so every
  value comes back a string unless a schema types it; it refuses flow style, which adr-019 accepts on one line; it
  crashes on a control character; it vendors ruamel.yaml 0.16 and pulls in two more packages; and its last release
  was in 2023.
- **A hand-written parser for the subset.** Removes the runtime package altogether. Not chosen: lorecraft would own
  a scanner for quoted and block scalars, multi-line plain scalars, flow collections, comments, CRLF and a BOM,
  refusing the rest on the right line. lorecraft parses frontmatter in other people's repositories, so the accept
  side cannot be judged from its own corpus.

## Consequences

- **Parsing is about 1.3× slower**: 25.8 to 33.7 ms on lorecraft's corpus, about 1% of a `check` run. It is
  accepted because frontmatter is small, so the difference is not noticeable.
- **The parser glue in `frontmatter.py` and `yaml/basic_yaml.py` is rebuilt.** ruamel.yaml wires its reader, scanner
  and parser through a loader object instead of PyYAML's mixin classes, and raises a reader error during the parse
  rather than at construction. The event walking, the core-schema resolution and adr-019's refusals sit on top of it.
- **Parity is proved once, not kept**: on the switch, the events inside adr-019's format match PyYAML's on the
  corpus. After that nothing compares with PyYAML; adr-019 defines the format, and its per-construct tests and the
  corpus check hold it. What a syntax error says, and on which line, is adr-019's.
- **The upgrade path is lighter**: lorecraft's runtime dependencies install from one pure wheel on any CPython,
  free-threaded builds included.
- **ruamel.yaml has one maintainer and has changed its API between minor versions**, so the pin stops below the
  next minor and each minor upgrade is a deliberate change that re-runs the tests.
- **PyYAML leaves lorecraft's own dependencies**, development ones included, so nothing lorecraft declares ties its
  CPython floor to PyYAML's wheels. A tool that depends on PyYAML may still bring it into the development lock; that
  is the tool's dependency, not lorecraft's.

## Checklist

- [ ] No module under `src/` or `tests/` imports `yaml`
- [ ] `pyproject.toml` declares `pyyaml` in no dependency group or extra, and lists `ruamel.yaml>=0.19,<0.20`
- [ ] `ruamel.yaml.clib` is not installed by lorecraft's runtime dependencies, and the `clib` extra is not requested
- [ ] `frontmatter.py` builds the value from ruamel.yaml's events and never calls a ruamel.yaml loader or constructor
- [ ] `frontmatter.py` and `yaml/basic_yaml.py` state no format rule of their own beyond adr-019's
- [ ] The switch's pull request records that, inside adr-019's format, the events on the corpus match PyYAML's in
  type, value, style and line
- [ ] A `\U` escape above `U+10FFFF` and a directive with an over-long version number are `FM002` on their line, not
  an exception

## References

- [adr-019](adr-019-frontmatter-format.md) - Foundation: The frontmatter format this parser reads
- [module-lorecraft-project](../code/module-lorecraft-project.md) - Related: The package whose frontmatter parser
  this decision changes
