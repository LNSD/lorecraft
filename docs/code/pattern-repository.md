---
name: "pattern-repository"
description: "Repository pattern: one concrete type owns stored entities and exposes domain-shaped reads with method-specific errors. Load when several callers read the same stored entity, when filesystem paths or storage errors leak into callers, or when designing a repository interface"
type: "core"
scope: "global"
---

# Repository (Storage Behind a Domain Interface)

## Rule

A repository owns access to one kind of stored entity. Callers ask for entities in domain terms; the repository alone knows how filenames, JSON, or another storage format represent them. Use one when several callers need to discover and retrieve the same entity. A single read used by one caller can remain a function.

Keep the repository concrete. Construct it with its storage location and inject it into callers that need it. A protocol or abstract base class earns its place only when a second real implementation exists. Its public methods should name useful operations, such as `list_schemas` and `get_header_schema`. Retrieval returns domain values; discovery may return a small record with the schema name and path so callers can identify files to inspect. Do not expose file handles, parser records, or filesystem exceptions.

Give each public method one exception family. That family may contain subclasses for failures callers handle differently. Translate I/O, decoding, and missing data at the repository boundary, retaining the original exception with `raise ... from exc`. Put the family beside the method that raises it. Callers can then handle one operation's failures without catching failures from another operation.

Keep validation of what the retrieved entity *means* above the repository. It reads and decodes; a checker decides whether a decoded schema accepts a document. Do not log in the repository: the caller has the context needed to report the failure.

## Examples

A checker needs a named schema. Passing a file path through the checker couples its API to the on-disk layout and forces it to handle JSON reading.

```python
# ❌ Bad — the caller knows where the file lives and how it is decoded.
def check_header(schema_path: Path, document: Document) -> list[Finding]:
    schema = json.loads(schema_path.read_text())
    return validate(document, schema)
```

```python
# ✅ Good — the repository returns the entity in domain terms. Its getter raises
# GetHeaderSchemaError for read and decode failures; validation stays here.
def check_header(schemas: Repository, corpus: CorpusName, document: Document) -> list[Finding]:
    schema = schemas.get_header_schema(corpus)
    return validate(document, schema)
```

## Why It Matters

One boundary makes changes to schema serialization local. Retrieval callers depend on schema names and values rather than filesystem paths; discovery callers receive the exact files available. Method-specific error families make recovery explicit: a caller listing available schemas can report a listing failure without accidentally handling a failed schema load as the same event.

## Pragmatism Caveat

Do not add a repository for one read in one place, or wrap an existing domain-facing repository with a second type that only forwards calls. Do not create a generic repository over unrelated entities merely to share a few lines of file access. A private decoding helper inside one concrete repository is enough for closely related stored forms.

## Checklist

- [ ] One concrete repository owns one entity family and its storage location
- [ ] Public methods express domain operations; retrieval returns domain values and discovery records include name and path
- [ ] No storage handle, parser record, or storage exception crosses its public boundary
- [ ] Each public method raises one documented exception family and chains the underlying cause
- [ ] The repository reads and decodes; callers apply the entity's business or validation rules
- [ ] Repository tests use real storage files rather than a fake implementation

## References

- [principle-information-hiding](principle-information-hiding.md) - Foundation: keep storage details inside one boundary
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: one entity family per repository

## External References

- [Martin Fowler — Repository](https://martinfowler.com/eaaCatalog/repository.html)
