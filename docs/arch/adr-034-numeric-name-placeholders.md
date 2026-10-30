---
name: "adr-034-numeric-name-placeholders"
description: "Match zero runs in corpus and namespace spec names to equal-width numeric document-name segments while preserving ordinary name chains. Load when changing how specs match numbered corpus documents"
type: "adr"
status: "proposed"
---

# Fixed-Width Numeric Name Placeholders

> [!NOTE]
> Proposed to supersede [adr-025-name-chain-model](adr-025-name-chain-model.md) in part: its strict hyphen-prefix matching rule where corpus and namespace spec names are matched to document names. Its remaining name-chain model stays in force until this record is accepted.

## Context

[prd-033](prd-033-numeric-name-placeholders.md) requires a zero run in a corpus or namespace spec name to match a numeric document-name prefix of exactly the same width (`FR-001` through `FR-003`). It also leaves sequence gaps and ordering to the repository (`FR-004`).

[adr-025](adr-025-name-chain-model.md) defines name chains through literal, hyphen-delimited prefixes. That rule works for names such as `python-fn-names` extending `python-fn`, but it cannot match the intended relationship between a spec name such as `adr-0000` and a numbered record such as `0001-subject`. Namespace matching has the same issue: `adr-0000-nspace` should apply to `0001-nspace-subject`.

## Decision

1. **A zero-only run is a numeric placeholder when matching a spec name to a document name.** At the position where the spec name is matched against a document-name prefix, a run consisting entirely of zeroes matches a segment consisting entirely of decimal digits when both have the same width. It does not match a segment of a different width or a segment containing letters. For example, the `0000` in `adr-0000` matches the leading `0001` in `0001-subject`.
2. **Match the remaining segments by the existing name-chain rule.** After a placeholder match, each following spec-name segment must equal the corresponding document-name segment, and the document name must either end there or continue with a hyphen-delimited segment. Thus `adr-0000-nspace` matches the beginning of `0001-nspace-subject`.
3. **Keep numeric placeholder matching in spec-to-document matching.** Corpus and namespace spec governance use the rule; document-to-document base chains and spec-to-spec hierarchy keep their existing literal hyphen-prefix behavior.
4. **Retain existing hierarchy resolution.** When several specs match a document, apply them from broad to narrow; resolve a document base from the longest existing literal document-name prefix. A missing intermediate name remains valid and does not make the chain fail.
5. **Treat sequence order as repository policy.** The placeholder describes digit width only. Lorecraft does not require sequences to start at one, be consecutive, or appear in numeric order.
6. **Accept digit-leading document and namespace names.** A document name or namespace may begin with a digit, such as `0001-subject`, and a namespace name such as `adr-0000-nspace` is valid, whether or not a placeholder governs it.
7. **Let a placeholder spec alone establish its corpus.** In `adr-0000`, the corpus is `adr` and `0000` is the numeric document-name prefix of that width. With `adr-0000.md` as the only spec, the corpus `adr` exists and `adr/0001-subject.md` is governed and checked; `adr/001-x.md` is not governed by it.

## Alternatives Considered

- **Keep literal matching and write a separate spec for each numbered prefix.** This is the simplest behavior change to avoid, but makes a spec set grow with each record and does not express the shared rules for a numbered corpus.
- **Add explicit wildcard syntax to spec names.** A marker such as `{number}` would make intent unambiguous, but introduces new syntax and migration guidance when the required fixed-width zero convention already communicates the width.
- **Treat every digit segment as a general variable.** This is compact, but loses the declared width: a spec could unexpectedly match records with differently sized numbers. Equal-width matching preserves the width a writer encoded.

## Compatibility and Migration

- Ordinary alphabetic and mixed-name chains continue to use the existing literal, hyphen-delimited prefix rule. Longest-existing-prefix resolution, broad-to-narrow application and gaps in a document chain remain unchanged.
- A zero-only segment in a corpus or namespace spec name gains meaning as a placeholder. A spec that previously intended a literal all-zero segment may now govern additional numbered documents. Its owner should rename that segment if the broader match is unwanted; a matching namespace can also add constraints through conjunction, so newly governed documents may reveal findings they did not previously receive.
- Numbered files must be recognized as document names for the new governance to take effect, so this decision widens document discovery and namespace parsing to digit-leading names. It does not validate numeric ordering.
- Digit-leading names are accepted with or without a placeholder. A file such as `1abc.md` that discovery silently left out of a corpus is now discovered and checked, and may report findings it never received.
- Existing numeric document names need no renaming to use the placeholder. Gaps are valid, and no order migration is required.

## Consequences

- Writers can express one corpus or namespace rule for records with a fixed-width numeric prefix.
- Existing specs with zero-only name segments may govern more documents, and those documents receive every applicable spec layer. Repositories using zeroes literally need to review those specs during adoption.
- The spec-to-document matching relation has a numeric case in addition to literal prefix matching. Document base chains and spec hierarchies remain unchanged, limiting the compatibility surface.
- Lorecraft does not police the sequence represented by the placeholder; repository writers retain control of numbering and gaps.

## Checklist

- [ ] A zero-only segment in a corpus or namespace spec name matches a document-name segment of decimal digits only when both have the same width
- [ ] Subsequent spec-name segments match equal document-name segments, and a document name may continue after the matched prefix
- [ ] `adr-0000.md` governs `0001-<subject>.md`
- [ ] `adr-0000-nspace.md` governs `0001-nspace-<subject>.md` alongside the corpus spec
- [ ] Ordinary literal hyphen-prefix matching and broad-to-narrow spec application remain intact
- [ ] Numeric placeholder matching does not alter document-to-document base chains or spec-to-spec hierarchy
- [ ] Digit-leading document names (`0001-subject.md`) are discovered and namespace names (`adr-0000-nspace`) parse
- [ ] `adr-0000.md` with no `adr.md` spec establishes the corpus `adr`, and `adr/0001-<subject>.md` is discovered and checked
- [ ] Gaps and document listing order receive no validation

## References

- [prd-033](prd-033-numeric-name-placeholders.md) - Source: Requirements `FR-001` through `FR-004`
- [adr-025](adr-025-name-chain-model.md) - Supersedes in part: Strict hyphen-prefix matching between corpus or namespace spec names and document names
