---
name: "pattern-facade"
description: "A small task-shaped interface coordinates several subsystem steps while leaving their responsibilities separate. Load when callers repeat the same multi-step workflow or must know the order of several collaborators"
type: "core"
scope: "global"
---

# Facade (One Entry Point for a Workflow)

## Rule

Use a facade when several callers must perform the same sequence across distinct collaborators. Give the
facade a method named for the caller's task, and keep the sequence and its failure boundary in one place.
Callers should not need to know which collaborator runs first or how an intermediate value reaches the next.

Keep the underlying operations in their owners. A facade coordinates discovery, loading, and checking; it
does not absorb file decoding, schema validation, or report formatting merely because it calls them. Pass
the collaborators it needs explicitly, and let callers use those collaborators directly when they need a
lower-level operation. Do not make the facade a second API that forwards every method unchanged.

## Examples

Two entry points check one document in the same way. Keep the sequence in one place:

```python
# ❌ Bad — each caller must know the steps and can silently omit schema selection.
def check_from_cli(path: Path, repository: Repository) -> HeaderCheckResult:
    document = resolve_document(path)
    schema = repository.get_header_schema(document.corpus)
    return validate_header(document, schema)


def check_from_editor(path: Path, repository: Repository) -> HeaderCheckResult:
    document = resolve_document(path)
    schema = repository.get_header_schema(document.corpus)
    return validate_header(document, schema)
```

```python
# ✅ Good — one task-shaped method owns the order; each collaborator keeps its job.
class DocumentChecks:
    def __init__(self, repository: Repository) -> None:
        self._repository = repository

    def check_header(self, path: Path) -> HeaderCheckResult:
        document = resolve_document(path)
        schema = self._repository.get_header_schema(document.corpus)
        return validate_header(document, schema)


def check_from_cli(path: Path, checks: DocumentChecks) -> HeaderCheckResult:
    return checks.check_header(path)


def check_from_editor(path: Path, checks: DocumentChecks) -> HeaderCheckResult:
    return checks.check_header(path)
```

## Why It Matters

When callers assemble the same workflow themselves, each is a place where order, error handling, or a new
step can drift. A facade gives the workflow one readable entry point. Its narrow surface also prevents a
caller from depending on intermediate data that the workflow may later stop exposing.

## Pragmatism Caveat

For one caller and a short sequence, a function at the call site is clearer. A facade is also unnecessary
when callers genuinely need different sequences. If its methods only forward calls, remove it; if it starts
owning every subsystem's rules, move those rules back to their owners.

## Checklist

- [ ] At least two callers need the same multi-step task, or the sequence is itself a stable API boundary
- [ ] The facade method names a caller task and owns the order of its steps
- [ ] Subsystems still own their own parsing, validation, and storage rules
- [ ] The facade does not merely forward every collaborator method
- [ ] Callers can use a lower-level collaborator directly when the full workflow is unnecessary

## References

- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: Keep each subsystem's rules with their owner
- [principle-information-hiding](principle-information-hiding.md) - Foundation: Expose the workflow without exposing its assembly
- [pattern-dependency-injection](pattern-dependency-injection.md) - Related: Supply the facade's collaborators explicitly

## External References

- [Refactoring Guru — Facade in Python](https://refactoring.guru/design-patterns/facade/python/example)
