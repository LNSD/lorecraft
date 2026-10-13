---
name: "adr-017-yaml-parser"
description: "Frontmatter is parsed with a pure-Python YAML parser, ruamel.yaml's event API in place of PyYAML's, with what lorecraft accepts as frontmatter and the FM002 lines and messages unchanged, so no runtime dependency carries a C extension. Load when changing how frontmatter is parsed, touching src/lorecraft/project/syntax/frontmatter.py, or adding or upgrading a YAML dependency"
type: "adr"
status: "proposed"
---

# A Pure-Python YAML Parser for Frontmatter

## Context

lorecraft reads a document's frontmatter as basic YAML: what JSON can hold, with plain scalars resolved by YAML
1.2's core schema, and anchors, aliases, explicit tags and keys that are not strings refused on their line.
`src/lorecraft/project/syntax/frontmatter.py` does this on top of PyYAML (`pyyaml>=6.0,<7`), its only user. It
drives PyYAML's low-level reader, scanner and parser and builds the value from the event stream itself; it never
calls `yaml.safe_load`. `FM002 invalid-yaml` reports the problem and the line the parser names.

That path is PyYAML's pure-Python code, so the libyaml C extension is never used. It still ships: PyYAML is
published as platform wheels with the compiled `_yaml` module, plus an sdist. A new CPython release or a
free-threaded build has to wait for PyYAML's wheels for it, or build the extension from source, so the dependency
holds lorecraft's upgrades back for code lorecraft does not run.

The candidates were compared on lorecraft's own corpus: every `*.md` under `docs/`, `skills/` and
`.claude/skills/` at `9e1d8b7`, 147 frontmatter blocks of 597 lines, on CPython 3.13. Parse time is the median of
30 passes; import cost is measured with hyperfine against a bare interpreter start.

| | PyYAML 6.0.3, pure path (today) | ruamel.yaml 0.19.1, pure | strictyaml 1.7.3 | Hand-written subset parser |
|---|---|---|---|---|
| Events with line marks | Yes | Yes; identical to PyYAML's on every corpus block | No; document API only | If written |
| `FM002` problem and line | Baseline | Same on every syntax-error probe | New messages; crashes on a control character | New wording |
| What is accepted | Baseline | Unchanged | Refuses flow style and duplicate keys | Must be re-proved case by case |
| Parse time, corpus | 25.8 ms | 33.7 ms (1.3×) | 111.3 ms (4.3×) | Not measured |
| Import cost | +9.3 ms | +10.8 ms | +19.4 ms | ≈0 |
| Distribution | Platform wheels with a C extension | One `py3-none-any` wheel; `clib` is an optional extra | Three packages, vendors ruamel.yaml 0.16 | None |

A full `lorecraft check` of this repository takes about 855 ms, so YAML parsing is a few percent of a run under
every option.

## Decision

1. **ruamel.yaml's pure-Python event API replaces PyYAML's** in `frontmatter.py`. The module reads ruamel.yaml's
   events, with their start marks, exactly as it reads PyYAML's today: the value is built from the events by
   lorecraft, never by a ruamel.yaml loader or constructor.
2. **What lorecraft accepts as frontmatter does not change.** The basic-YAML rules in the module's docstring hold
   as written: the same blocks decode to the same values, and the same blocks are refused.
3. **`FM002` reports the same problem and the same line** for every block it reports today. ruamel.yaml's errors
   are mapped into `InvalidYamlFrontmatter` as PyYAML's are, taking the problem mark, then the context mark.
4. **The two places a plain `ValueError` escapes the scanner stay closed.** ruamel.yaml shares PyYAML's two gaps, a
   `\U` escape above `U+10FFFF` and a `%YAML` version number too long to convert, and each is raised as a scanner
   error on its line, as today.
5. **`ruamel.yaml` is a runtime dependency, pinned `>=0.19,<0.20`**, and its C extension is never installed:
   `ruamel.yaml.clib` is not a dependency of lorecraft, and the `clib` extra is not requested.
6. **`pyyaml` is not a runtime dependency**, and no module under `src/` imports `yaml`.

## Alternatives Considered

- **Keep PyYAML.** The fastest of the pure-Python options and the cheapest to import, with no code to change. Not
  chosen: it keeps the C extension in every install and its platform wheels on lorecraft's upgrade path, which is
  the cost this decision removes.
- **strictyaml.** Its own API refuses anchors, aliases and tags. Not chosen: it gives no event access, so every
  value comes back a string unless a schema types it; it refuses flow style and duplicate keys, which changes what
  lorecraft accepts; it crashes on a control character; it vendors ruamel.yaml 0.16 and pulls in two more packages;
  and its last release was in 2023.
- **A hand-written basic-YAML subset parser.** Removes the runtime package altogether. Not chosen: lorecraft would
  own a YAML scanner, estimated at 700–1,000 lines plus its tests, that must accept everything the module's
  docstring promises (flow collections, quoted and block scalars, multi-line plain scalars, comments, CRLF and a
  BOM) and refuse the rest on the right line. lorecraft parses frontmatter in other people's repositories, so the
  accept side cannot be judged from its own corpus, and every `FM002` message would change.

## Consequences

- **Parsing is about 1.3× slower**: 25.8 to 33.7 ms on lorecraft's corpus, about 1% of a `check` run. It is
  accepted because frontmatter is small, so the difference is not noticeable.
- **The parser glue in `frontmatter.py` is rebuilt**, an estimated 60–100 lines. ruamel.yaml wires its reader,
  scanner and parser through a loader object instead of PyYAML's mixin classes, and raises a reader error during
  the parse rather than at construction, so `_BasicYamlParser` and the reader-error branch of
  `decode_frontmatter` change. The event walking, the core-schema resolution and the refusals carry over with new
  imports.
- **Parity is proved by tests**: the event streams and the `FM002` problem and line match today's on the corpus and
  on the syntax-error probes, before PyYAML is removed.
- **The upgrade path is lighter**: lorecraft's runtime dependencies install from one pure wheel on any CPython,
  free-threaded builds included.
- **ruamel.yaml has one maintainer and has changed its API between minor versions**, so the pin stops below the
  next minor and each minor upgrade is a deliberate change that re-runs the parity tests.
- **PyYAML may stay in the development lock** through tools that depend on it; only the runtime dependency goes.
- **What stays true**: the four outcomes of `decode_frontmatter`, the basic-YAML rules, and every frontmatter
  diagnostic users see.

## Checklist

- [ ] No module under `src/` imports `yaml`
- [ ] `pyproject.toml` lists no `pyyaml` runtime dependency, and lists `ruamel.yaml>=0.19,<0.20`
- [ ] `ruamel.yaml.clib` is not installed by lorecraft's runtime dependencies, and the `clib` extra is not requested
- [ ] `frontmatter.py` builds the value from ruamel.yaml's events and never calls a ruamel.yaml loader or constructor
- [ ] Event parity tests pass on the corpus: type, value, style, anchor, tag and line match PyYAML's
- [ ] `FM002` parity tests pass on the syntax-error probes: same problem, same line
- [ ] A `\U` escape above `U+10FFFF` and an over-long `%YAML` number are `FM002` on their line, not an exception

## References

- [module-lorecraft-project](../code/module-lorecraft-project.md) - Related: The package whose frontmatter parser
  this decision changes
