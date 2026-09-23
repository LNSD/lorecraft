---
name: "principle-law-of-demeter"
description: "Law of Demeter — a unit talks to its immediate collaborators, never through them to reach something further. Load when reviewing call chains, attribute access patterns, or coupling concerns"
type: "principle"
scope: "global"
---

# Law of Demeter (Principle of Least Knowledge)

## Rule

A function or method may only talk to its immediate collaborators. Do not reach through chains of values to
get at something buried deep in the object graph. A method `m` of a class `T` may only call methods on `T`
itself (`self`), on values passed as arguments to `m`, on values `m` created, and on values held in `T`'s own
attributes.

If you write `a.b().c().do_something()` — or `a.b.c.do_something()` — you are violating the principle. Stop at
`a.b()`: if you need something from `c`, ask `a` (or `b`) to hand you the value, or accept the value as a
parameter.

**Not violations**: chains where every link is the same logical value. Fluent builder chains
(`CheckSpec.builder().corpus('code').budget(400).build()`), iterator and generator chains
(`itertools.islice(filter(pred, findings), n)`), comprehensions over a collaborator's return value
(`[section.heading for section in document.outline()]`), and branching on a status a direct collaborator
returned (`binding = registry.spec_for(corpus); binding.spec.validate(frontmatter)`) are not reach-through —
the returned value is that collaborator's own answer.

## Examples

1. **Ask the collaborator, don't navigate its internals**
   A registry owns a `dict[str, FormatSpec]`, the key scheme, and the "is this corpus specified" decision.

```python
# ❌ Bad — reaches through the registry into its dict and through the spec into its schema.
# This caller now depends on the key being the corpus name (not the document type), on specs
# being stored in a plain dict, and on the spec exposing a raw schema. Any of the three
# changing breaks it, and nothing in the type system says this caller exists.
def check_frontmatter(registry: SpecRegistry, document: Document) -> list[Finding]:
    spec = registry._specs[document.corpus]
    return spec._schema.validate(document.frontmatter)
```

```python
# ✅ Good — one call to the immediate collaborator, which answers the question completely.
# This caller knows two things: ask the registry for a binding, or report why it cannot have one.
def check_frontmatter(registry: SpecRegistry, document: Document) -> list[Finding]:
    """Check a document's frontmatter against the spec its corpus declares.

    Args:
        registry: Spec registry owning the format spec for this corpus.
        document: Document whose frontmatter is checked.

    Returns:
        One finding per frontmatter field that violates the spec.

    Raises:
        UnspecifiedCorpusError: If the registry has no spec for this corpus.
    """
    binding = registry.spec_for(document.corpus)
    if binding.status is SpecStatus.UNSPECIFIED:
        raise UnspecifiedCorpusError(binding.reason)
    return binding.spec.validate(document.frontmatter)
```

2. **Receive the value, not the object graph that contains it**
   A schema resolver needs a docs directory and a way to read files. It should take exactly those two
   things.

```python
# ❌ Bad — the resolver is handed the whole checker session and digs for what it needs. It is
# coupled to the session's shape three levels down, and it cannot be unit tested without
# standing up a full session: spec registry, skill loader, settings parser and all.
class SchemaResolver:
    def __init__(self, session: CheckerSession) -> None:
        self._session = session

    def resolve(self, corpus: str) -> Path | None:
        root = self._session.workspace.settings.paths.docs_root  # three levels of reach-through
        ...
```

```python
# ✅ Good — declare the two collaborators the resolver actually uses. The caller that already
# holds the session does the navigation once, at the seam. Tests construct this with a tmp_path
# and a two-line lambda.
class SchemaResolver:
    def __init__(self, docs_root: Path, read_file: Callable[[Path], bytes]) -> None:
        self._docs_root = docs_root
        self._read_file = read_file

    def resolve(self, corpus: str) -> Path | None:
        """Locate the frontmatter schema for ``corpus`` under the docs directory."""
        # uses only its own two attributes
```

## Why It Matters

Reach-through chains turn a private implementation detail into a public contract by accident. When a registry
changes its lookup key from the corpus name to `(corpus, document_type)`, every caller that read its dict
breaks — and nothing told you those callers existed. Keeping to immediate collaborators lets a module
restructure its internals as long as its methods keep their meaning.

The second cost is testability: a class that navigates `session.workspace.settings.paths.docs_root` can only
be exercised by building a whole session, so it ends up covered by a slow end-to-end run over a real
document tree, or not at all. A class that takes a `Path` and a read callable is tested with `tmp_path` and
three lines.

## Pragmatism Caveat

A short reach-through is occasionally the honest choice: navigating a plain data structure you own (a parsed
frontmatter mapping, an outline you just built) is reading data, not coupling. The rule targets navigation
through _behavioral_ values that could hide their internals. When you deliberately reach through one, add a
comment explaining why the alternatives (a delegating method on the direct collaborator, or passing the value
in) were rejected. An undocumented violation is always wrong.

## Checklist

Before committing code, verify:

- [ ] No expression navigates two or more levels into another class's attributes to reach behavior
- [ ] Functions accept the values they use (a path, a reader, a handle) rather than a container to dig through
- [ ] Cross-module access goes through public functions and methods, never through another module's internal
      collections or underscore-prefixed state
- [ ] Fluent chains on one logical value (builders, iterators, comprehensions, a returned status object) are
      not mistaken for violations
- [ ] Any deliberate reach-through is local and carries a comment with its rationale

## References

- [principle-single-responsibility](principle-single-responsibility.md) - Related: A class that must be navigated
  deeply usually owns too much

## External References

- [Law of Demeter — Principle of Least Knowledge](https://dev.to/dazevedo/law-of-demeter-principle-of-least-knowledge-35l2)
