---
name: "adr-013-namespace-extension"
description: "A namespace extension layers onto its base by conjunction for every kind of document, code specs and feat specs as well as meta specs: a document's base chain is separate from the meta specs that govern it, and loading a document loads its whole chain, base first. Load when writing or reviewing a code spec or feat spec that extends another, changing which documents /code-rules or /feat-discovery load, or changing what lorecraft inspect shows about a name's chain"
type: "adr"
status: "proposed"
---

# Namespace Extension by Conjunction

## Context

Lorecraft extends by namespacing: a hyphenated name continues a shorter one, and the longer name specializes what
the shorter one states in general. Three kinds of document extend this way:

| Kind | Base | Extensions, broad to narrow |
|------|------|-----------------------------|
| Meta specs, `docs/__meta__/` | `feat`, the corpus meta spec | `feat-cli`, then a `feat-cli-check` were it added |
| Code specs, `docs/code/` | `python-fn.md` | `python-fn-names.md`, `python-fn-unchecked.md` |
| Feat specs, `docs/feat/` | `spec.md` | `spec-structure.md`, then `spec-structure-outline.md` |

For meta specs, [adr-006](adr-006-specifications.md) decides how an extension takes effect: by conjunction,
each governing meta spec applied on its own, so an extension adds or tightens and never relaxes. Nothing decides
it for code specs and feat specs. [spec](../feat/spec.md) defines a name's base for every kind, and each document
names its base under References, but nothing hands an agent a document's base: `/code-rules` tells it to take the
most specific match and add a broader document only when the task turns on what it owns, and `/feat-discovery`
follows References only when relevant. An agent loading `python-fn-names.md` can miss what `python-fn.md` states
about every function.

## Decision

1. **An extension layers onto its base by conjunction, whatever kind of document it is.** For a meta spec,
   adr-006 states the rule. For a code spec or a feat spec, everything its base states still holds for what the
   extension covers, and the extension adds to it or narrows it; it never relaxes or contradicts it.
   `python-fn-names.md` adds naming rules to what `python-fn.md` states about functions, and
   `spec-structure-outline.md` describes one part of what `spec-structure.md` describes as a whole.
2. **A name's chain is the same for every kind.** A name's base is the longest existing name it continues with a
   hyphen, counted in hyphen-delimited tokens, so no two names in a chain tie. A chain may be of any depth. A name
   whose base has no file continues from the nearest existing name, as today: `python-fn-names.md` extends
   `python-fn.md`, though no `python.md` exists, and that is not an error.
3. **A document's base chain and its governing meta specs are two chains.** The meta specs that govern a
   document follow from adr-006: the corpus meta spec, then the namespace meta specs. Its base chain is the
   documents its own name continues, in its own corpus. `python-fn-names.md` is governed by `code` < `code-python`,
   and its base chain is `python-fn` < `python-fn-names`. Neither chain is derived from the other.
4. **Loading a document loads its base chain, base first.** `/code-rules` and `/feat-discovery` read every document
   in a matched document's chain, from the broadest down to the match.
5. **A namespace meta spec adds no frontmatter field.** The corpus schema declares every field and stays
   closed, and a namespace schema only narrows a field the corpus schema declares, so each schema can still be
   checked on its own.
6. **`lorecraft inspect` shows both chains**, under separate names: the meta specs governing a document, as it
   does today, and the document's base chain.

## Alternatives Considered

- **Override.** The narrowest document that exists stands alone and replaces its base for what it covers, so each
  file reads on its own and loading a document loads one file. Not chosen: every extension restates what it keeps of
  its base, and the copies drift; and it turns any contradiction into a relaxation, which no document in the
  repository needs. adr-006 rejects it for meta specs for the same reasons.
- **Loading the most specific match only**, as `/code-rules` does today. It costs the fewest tokens, but an agent
  following one document misses the rules its base still applies. Today a chain is at most two documents in
  `docs/code/` and three in `docs/feat/`.
- **A missing base as an error.** It would make every chain explicit, at the cost of a base document for each prefix
  group in `docs/code/` that has none, such as `python`, `pattern` and `principle`. For most of those groups a
  namespace meta spec already states what they share.
- **A namespace schema that adds a field**, with the corpus schema closed over the fields every layer declares, the
  way JSON Schema's `unevaluatedProperties` works. Not chosen: no schema could then be checked on its own, and no
  meta spec in the repository adds a field.

## Consequences

- **`/code-rules` changes its selection rule** from the most specific match to the matched document's whole chain,
  and `/feat-discovery` reads a matched document's base chain rather than following References when relevant.
- **Each load reads more**: at most one more document in `docs/code/` and two more in `docs/feat/`, at today's depth.
- **`lorecraft inspect` gains a document's base chain** beside the meta specs that govern it.
- **A contradiction between a code spec or feat spec and its base is found in review.** Their rules are prose, and
  no check can decide it.
- **What stays true:** how meta specs govern documents is adr-006's, unchanged. The prefix groups in
  `docs/code/` without a base document stay valid.

## Checklist

- [ ] A code spec or feat spec adds to or narrows what its base states, and neither restates nor contradicts it
- [ ] An extension names its base under References, and a base names none of its extensions
- [ ] A name's base is the longest existing name it continues with a hyphen; a name whose base has no file continues
  from the nearest existing one, and is not an error
- [ ] `/code-rules` and `/feat-discovery` load a matched document's whole base chain, base first
- [ ] `lorecraft inspect` shows a document's governing meta specs and its base chain under separate names
- [ ] A namespace meta spec's frontmatter schema narrows only fields its corpus schema declares

## References

- [#208](https://github.com/LNSD/lorecraft/issues/208) - Source: Whether a namespace extension layers onto its base or
  overrides it
- [adr-006-specifications](adr-006-specifications.md) - Foundation: Conjunction for meta specs
- [spec](../feat/spec.md) - Foundation: A name's base, and references pointing to the base
