---
name: "principle-information-hiding"
description: "Information Hiding — reveal as little as possible: a leading underscore is the default for every name and every helper module, a package's `__all__` is its whole public surface and the only widening that counts, reaching into another subpackage's underscored module is a violation even though nothing prevents it, and every re-export into `__init__.py` needs a reason, because widening is cheap and retracting is not. Load when adding a name to a package's surface, deciding what an `__init__.py` re-exports, or reviewing what a subpackage reveals"
type: "principle"
scope: "global"
---

# Information Hiding (Reveal As Little As Possible)

## Rule

A module is defined by the design decision it **hides**. Its surface reveals as little as possible about how it
works, so the decision can change without any caller learning that it did.

Operationally, in Python:

1. **A leading underscore is the default.** `_normalize_heading`, `_schema_cache`, `_SectionIndex`. A name
   *without* one is a promise: it says that callers you cannot see, in code you will never read, may depend on
   this name, this signature, and this behaviour. Write the underscore first and remove it when a caller
   outside the module genuinely needs the name.
2. **A package's `__all__` is its surface.** The `__all__` in a package's `__init__.py` is the list of names the
   package supports, and adding to it is the only widening that counts. Everything reachable by a longer import
   path is reachable the way a screwdriver reaches the inside of a radio.
3. **Reaching into another subpackage's underscored module is the violation.** Nothing raises, nothing warns,
   the import simply succeeds — which is exactly why the convention has to carry the weight. An underscore is a
   request, and a request that is honoured only when enforced is not a convention at all.
4. **A module-private helper module takes a leading underscore in its name.** A helper module named
   `_heading_parsing` announces at every import site that it belongs to its package; one named
   `heading_parsing` reads as part of the surface whether or not anyone meant it to.
5. **Re-exporting a name into `__init__.py` is a decision with a reason**, not a convenience for shortening an
   import in one call site. Each re-export is a name the package now supports forever.

## Examples

1. **The package surface is an explicit list, not whatever the modules happen to define**
   A star-import surface grows every time anyone adds a name to any module in the package.

```python
# ❌ Bad — the package re-exports whatever its modules define, so the surface changes without
# anyone editing this file. A developer adding a `normalize_heading` helper to the outline
# module published it to every consumer in the same commit, and two other repositories were
# importing it before anyone noticed it was meant to be internal.
from .frontmatter import *
from .outline import *
from .registry import *
```

```python
# ✅ Good — the surface is written down, reviewed as a diff, and unchanged by anything added
# inside the modules it draws from.
from .frontmatter import FrontmatterChecker
from .outline import OutlineChecker
from .registry import checker_for, register_checker

__all__ = [
    'FrontmatterChecker',
    'OutlineChecker',
    'checker_for',
    'register_checker',
]
```

2. **Hide the decision, not just the data**
   A class whose surface mirrors its representation has hidden nothing, however underscored its attributes are.

```python
# ❌ Bad — the attribute is private, but every method re-exposes the representation one call
# at a time. Switching the sorted list of pairs for an interval tree is now a breaking change
# to four public methods, which is exactly what encapsulation was supposed to prevent — and a
# caller that got the list back mutated it in place, leaving the index unsorted and the
# bisect silently wrong, so findings were reported under the preceding heading.
class SectionIndex:
    def __init__(self) -> None:
        self._entries: list[tuple[int, str]] = []

    def entries(self) -> list[tuple[int, str]]:
        return self._entries

    def sort(self) -> None: ...

    def bisect(self, line_number: int) -> int: ...

    def append(self, first_line: int, heading: str) -> None: ...
```

```python
# ✅ Good — the surface is the question callers actually ask. The representation, the
# ordering, and the search strategy are one class's business, and any of them can change
# without a caller noticing.
class SectionIndex:
    """Maps a line of a document to the section containing it."""

    def insert(self, first_line: int, heading: str) -> None:
        """Record that the section ``heading`` begins at ``first_line``."""

    def covering(self, line_number: int) -> str | None:
        """Return the heading of the section containing ``line_number``, or None."""
```

3. **Depend on the published surface, not on someone else's underscore**
   The import succeeds either way. Only one of them keeps working.

```python
# ❌ Bad — a sibling subpackage reaches past the surface for a helper it found convenient.
# Nothing prevented the import, so nothing announced the coupling either: the frontmatter
# package rewrote `_validate_against_schema` to take a compiled schema instead of a schema
# mapping, its own tests passed, and the skill checker broke in a release nobody connected
# to that change.
from ..frontmatter._schema import _validate_against_schema


def check_skill(document: Document) -> list[Finding]:
    return _validate_against_schema(document.frontmatter, SKILL_SCHEMA)
```

```python
# ✅ Good — the dependency goes through a supported name. If the frontmatter package wants
# that helper reusable, it publishes it deliberately and owns it; until then, the skill
# checker asks for the operation rather than the internals that implement it.
from ..frontmatter import FrontmatterChecker


def check_skill(checker: FrontmatterChecker, document: Document) -> list[Finding]:
    return checker.check(document)
```

## Why It Matters

Parnas's argument has not aged: you decompose a system by what is **likely to change**, and each module hides
one of those decisions. A module that reveals its representation has published a decision instead of hiding
one, and every consumer becomes a reason not to revise it.

The spine of the rule is the asymmetry between widening and retracting, and Python sharpens it to a point.
Widening costs one line: drop an underscore, add a string to `__all__`. Retracting costs a search you cannot
actually perform — there is no visibility checker and no compiler to tell you who reached for the name, and
imports can be built from strings at runtime, so even a grep across every repository you know about is a lower
bound rather than an answer. The first symptom of a retraction is usually somebody else's `ImportError`, in a
codebase you did not know existed.

That is also why review is where this is enforced. A Rust compiler rejects the call that reaches past `pub`; an
underscore rejects nothing. The import that violates this principle is syntactically perfect, passes every
test, and looks in the diff exactly like an import that does not. Nobody but a reviewer is ever going to catch
it, so a reviewer has to be looking.

## Pragmatism Caveat

The rule is about what a module **reveals**, not about ceremony. A dataclass with no invariant — a settings
record parsed at the edge, a finding about to be rendered into a report — has plain public attributes, because
no decision is being hidden and accessors would add nothing but noise. Where an invariant does exist, the
attribute takes an underscore and the constructor enforces it.

Test access is not a reason to widen. A test in the same package imports the underscored name directly; that is
a deliberate, reviewable coupling between a test and the implementation it is testing, and it is nothing like
adding the name to `__all__`, which offers it to everyone forever.

Double-underscore name mangling is not a stronger underscore. It exists to avoid attribute collisions in
subclasses, not to hide anything, and using it for privacy mostly annoys the debugger.

When you deliberately expose more than a caller strictly needs — a type a downstream consumer must name in its
own annotations, a helper published so a repository can write a check of its own — say why in the docstring at
the declaration and list it in `__all__` on purpose. An undocumented public name on something the package does
not intend to support is indistinguishable from an oversight, and will be depended on as though it were
supported.

## Checklist

Before committing code, verify:

- [ ] Every new name starts with an underscore unless a caller outside its module needs it
- [ ] Each package's `__init__.py` declares an explicit `__all__`; no `import *` builds the surface
- [ ] Every name added to `__all__` has a caller that needs it and an owner willing to support it
- [ ] No module imports an underscored name or module from another subpackage
- [ ] Helper modules that belong to one package are named with a leading underscore
- [ ] A class's public surface is the questions callers ask, not a mirror of its representation
- [ ] No name was made public solely so a test could reach it
- [ ] Public attributes appear only on records with no invariant to protect
- [ ] Any deliberate over-exposure is documented in the docstring at the declaration

## References

- [principle-single-responsibility](principle-single-responsibility.md) - Related: A module can only own one
  responsibility if callers cannot reach past its surface
- [principle-law-of-demeter](principle-law-of-demeter.md) - Related: A surface that reveals its internals is
  what makes reach-through possible

## External References

- [On the Criteria To Be Used in Decomposing Systems into Modules — D. L. Parnas](https://dl.acm.org/doi/10.1145/361598.361623)
- [PEP 8 — Public and internal interfaces](https://peps.python.org/pep-0008/#public-and-internal-interfaces)
- [Information Hiding and Encapsulation — David Gries](https://www.cs.cornell.edu/courses/JavaAndDS/files/infoHiding.pdf)
- [Least Privilege Principle — OWASP](https://owasp.org/www-community/controls/Least_Privilege_Principle)
