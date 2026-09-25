---
name: "pattern-dependency-injection"
description: "Supply a collaborator to the code that uses it instead of constructing or locating it there. Load when a class hides a repository or service constructor, when callers need different implementations, or when setup policy leaks into domain logic"
type: "core"
scope: "global"
---

# Dependency Injection (Explicit Collaborators)

## Rule

When a class needs a collaborator, accept it in the constructor; when one operation alone needs it, accept
it as a parameter. Construct concrete collaborators at the application boundary and pass them inward. The
receiving code states what it needs and can be read without searching for global configuration or an
internal constructor.

Use a concrete type while there is one implementation. Introduce a `Protocol` or abstract base only when
multiple real implementations need one contract; an injectable parameter does not require an interface
hierarchy. Keep the collaborator required when the operation cannot work without it. Do not default it to
`None` and silently construct a fallback inside the consumer.

## Examples

A checker needs stored schemas. Make the dependency visible at construction:

```python
# ❌ Bad — the checker silently chooses a storage location and constructs its own dependency.
class HeaderChecks:
    def __init__(self) -> None:
        self._schemas = Repository(Path('docs/__meta__'))

    def schema_for(self, corpus: CorpusName) -> HeaderSchema:
        return self._schemas.get_header_schema(corpus)
```

```python
# ✅ Good — setup chooses the repository; the checker states the collaborator it needs.
class HeaderChecks:
    def __init__(self, schemas: Repository) -> None:
        self._schemas = schemas

    def schema_for(self, corpus: CorpusName) -> HeaderSchema:
        return self._schemas.get_header_schema(corpus)


schemas = Repository(specs_dir)
checks = HeaderChecks(schemas)
```

## Why It Matters

Hidden construction couples a consumer to a concrete location and makes failures appear during use rather
than setup. Explicit collaborators make the construction path visible, permit a caller to reuse one
repository, and let an integration test supply a repository backed by temporary files. They also keep
configuration and domain work in separate places.

## Pragmatism Caveat

Do not inject immutable constants, pure standard-library functions, or every tiny helper. Directly calling
them is easier to follow. Do not add a container, service locator, or protocol merely to pass one concrete
object through a few constructors. When an operation has no meaningful alternative collaborator and no
setup policy to isolate, direct construction may be simpler.

## Checklist

- [ ] A required collaborator appears in the constructor or the operation signature
- [ ] Concrete collaborators are constructed at the application boundary
- [ ] The consumer does not look up a global service or build a fallback collaborator
- [ ] An interface is introduced only for a real shared contract, not just to enable injection
- [ ] A container is not added merely to pass a few concrete collaborators

## References

- [principle-information-hiding](principle-information-hiding.md) - Foundation: Keep setup choices outside the consumer
- [pattern-repository](pattern-repository.md) - Related: Inject a concrete repository into its callers
- [pattern-facade](pattern-facade.md) - Related: Supply the collaborators a workflow facade coordinates
- [pattern-callable-factory](pattern-callable-factory.md) - Related: Inject a callable when the consumer must build instances later

## External References

- [Martin Fowler — Inversion of Control Containers and the Dependency Injection pattern](https://martinfowler.com/articles/injection.html)
- [Python docs — Protocols](https://docs.python.org/3.12/library/typing.html#nominal-vs-structural-subtyping)
