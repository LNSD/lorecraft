---
name: "module-lorecraft-schemas"
description: "The lorecraft.schemas package's responsibility, role, boundary and invariants: typed schema identities, provenance, immutable inputs and pure lookup without acquisition, project queries or a second cache. Load when adding or changing schema references, input origins or registry resolution"
type: "pkg"
scope: "pkg:lorecraft.schemas"
---

# The `lorecraft.schemas` Package

## Responsibility

Provide the typed vocabulary and pure lookup for schema inputs already acquired by a workspace loader or shipped
with Lorecraft. It changes when schema identity, provenance or the immutable input representation changes.

## Role

**Derivation boundary.** It lets project queries and loaders share schema identity and input values without making
the registry a loader, query layer or cache. Its import layer sits below `lorecraft.agents` and above `lorecraft.vfs`.

## Belongs Here

- Structure and frontmatter schema kinds, references, repository and bundled origins, and immutable schema inputs.
- In-memory lookup of an input by its typed reference.
- `EmptySchemaReferenceIdentityError`, `EmptyRepositoryLayerError` and `EmptyBundledOriginIdentityError` carry rejected identity values.
- `SchemaOriginMismatchError` carries a reference and bundled origin with different identities; registry lookups have typed missing and duplicate reference errors.

## Belongs Elsewhere

| Code that… | Belongs in |
|---|---|
| Reads workspace files and records source inputs | `lorecraft.project` |
| Resolves applicable schemas from governance or memoizes derived facts | `lorecraft.project` and its database |
| Parses or validates JSON Schema documents | `lorecraft.jsonschema` |
| Computes outline, budget or parsed structure facts | Their existing project domain |

## Invariants

- Values are immutable and references identify a schema kind and stable source identity, never an invented path or `$id`.
- Empty identity and layer fields raise their operation-specific Lorecraft errors with the rejected values attached.
- Structure and frontmatter are the only schema kinds; either kind may have repository or bundled provenance. Parsed structure specifications are not registry inputs.
- Repository origins retain a root-relative path and governing layer; bundled origins retain a stable identity and no fabricated path.
- A bundled origin identity must match its schema reference identity so the provenance names the referenced schema, regardless of kind; `SchemaOriginMismatchError` carries this mismatch.
- The bundled Agent Skills input carries the model-rendered JSON Schema as registry data, while schema queries return its Pydantic validator; do not substitute JSON Schema validation or infer equivalent diagnostic behavior from that document.
- Registry resolution examines only the supplied immutable inputs. It performs no filesystem or external resource reads and holds no mutable cache.
- This package imports no project database, query, workspace-loading or filesystem modules.

## Examples

```python
# ❌ Bad — registry resolution reaches the live tree, so the same loaded model can answer differently later
def resolve(reference: SchemaReference, root: Path) -> SchemaInput:
    return parse_schema((root / reference.identity).read_text())
```

```python
# ✅ Good — the loader supplies immutable inputs once, and lookup answers only from that model
registry = SchemaRegistry.from_inputs(loaded_schema_inputs)
schema_input = registry.resolve(reference)
```

## Checklist

Before committing code, verify:

- [ ] Schema identity includes both kind and stable identity; empty identities raise `EmptySchemaReferenceIdentityError`
- [ ] Inputs preserve immutable document values and provenance independently of kind; bundled origin identities must match their references
- [ ] Empty repository layers and bundled identities raise typed Lorecraft errors with their input values attached
- [ ] Lookup is deterministic and refuses missing identities; registry construction refuses duplicate references with `DuplicateSchemaReferenceError`
- [ ] No registry operation reads files, resolves external resources or memoizes results
- [ ] No import points to project queries, database or workspace loading

## References

- [adr-028-schema-registry](../arch/adr-028-schema-registry.md) - Foundation: Schema identities, origins and registry ownership
- [adr-027-subject-keyed-queries](../arch/adr-027-subject-keyed-queries.md) - Foundation: Typed subject identities and database-owned query reads
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: Keep pure lookup separate from loading and validation
