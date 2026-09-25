---
name: "python-modules"
description: "Package layout and imports: no module beside a same-named package, relative inside and absolute in tests, the two-dot cap, `__all__`, `__init__.py` re-exports, optional-dependency degradation, and `noqa` form. Load when adding a module or package, writing an import, exporting a symbol, or suppressing a lint rule"
type: "core"
scope: "global"
---

# Package Layout and Imports

A package's shape is the first thing a reader navigates and the last thing anyone wants to change, so it has to
be legible from the file tree alone: one name means one thing, an import's form says whether it crosses a
package boundary, and `__init__.py` is where the package states its surface rather than where behaviour hides.

Import **ordering** inside a file is the formatter's job and is not argued about here (§8). What a module's
symbols are called is owned by [python-naming](python-naming.md). The `if TYPE_CHECKING:` block's contents and
the quoting it requires are owned by [python-typing](python-typing.md).

## 1. A Package Is a Directory, and No Module Sits Beside a Package of the Same Name

A unit with more than one file is a directory with `__init__.py`. A module `outline.py` **never** sits
alongside a package `outline/` in the same parent.

When both exist, the package wins import resolution unconditionally. The module is unreachable — but it is
still a file in the tree that a reader finds, a grep hits, and a reviewer edits, and its imports are still
scanned by tooling. It is dead code wearing a live name, and the usual signal for dead code (nothing imports
it) is absent, because `from lorecraft.outline import X` looks exactly like an import of it.

```
# ❌ Bad — outline.py is unreachable; `from lorecraft.checks.outline import OutlineReport`
# resolves into the package, so edits to the module change nothing and the failure
# is a confusing ImportError naming a symbol that is plainly right there
lorecraft/checks/
    outline.py
    outline/
        __init__.py
        parser.py
```

```
# ✅ Good — one name, one location
lorecraft/checks/
    outline/
        __init__.py
        parser.py
        report.py
```

Promoting a module to a package means moving it in: `outline.py` becomes `outline/__init__.py` or
`outline/<something>.py` re-exported from `__init__.py`, in the same commit.

## 2. Relative Imports Within the Package, Absolute in Tests

Inside `src/`, a module importing from its own package or a sibling package uses a relative import:
`from .report import OutlineReport`, `from ..schema.loader import SchemaLoader`. Test modules import the
library absolutely: `from lorecraft.checks.outline import OutlineReport`.

The two forms are answering different questions. Inside the package, the relative form says "this is our own
code" at a glance and survives the package being renamed or vendored. In tests, the absolute form exercises the
package the way a user imports it, so a broken `__init__.py` export fails a test instead of being routed
around.

```python
# ❌ Bad — inside the library. The package's own name is baked into every file, so the
# name cannot change without touching all of them, and nothing distinguishes an
# internal import from a third-party one at a glance
from lorecraft.checks.outline.report import OutlineReport
from lorecraft.schema.loader import SchemaLoader
```

```python
# ✅ Good — inside the library
from ..schema.loader import SchemaLoader
from .report import OutlineReport
```

```python
# ✅ Good — in a test, importing the way a user would
from lorecraft.checks.outline import OutlineReport
```

## 3. Three Dots Means the Module Is in the Wrong Place

Relative imports are capped at two dots. `from ...x import y` does not appear.

At three dots the reader can no longer tell what is being imported without reconstructing the file's depth in
the tree, and the import silently resolves to something else the moment either module moves. But the real
signal is structural: a module reaching three levels up is either misplaced, or the thing it reaches for is.
Fix the placement rather than the path — move the shared type to a package both sides sit under, or move the
module closer to what it depends on.

```python
# ❌ Bad — unreadable at the use site, and it breaks without an error the day this
# module is nested one level deeper
from ...checks.registry import CheckerRegistry
```

```python
# ✅ Good — the dependency was shared by several subtrees, so it moved to a package both
# reach with one or two dots
from ..registry import CheckerRegistry
```

## 4. `__all__` Declares a Package's Surface

Every package `__init__.py` that re-exports anything declares `__all__` listing exactly those names.

Without it the package's surface is "whatever happens to be bound at module level" — including every module
name pulled in as a side effect of an import and every symbol a re-exported module brought along. `__all__` is
the difference between a surface someone chose and a surface that accumulated. It also makes a removal visible
in the diff: deleting a public name shows up as a line removed from `__all__`, not as a symbol quietly no
longer importable.

```python
# ❌ Bad — `from lorecraft.checks.outline import *` now also exports `parser`, `report`,
# `logging`, and every name those modules re-exported. A later refactor that stops
# importing `logging` here is a breaking change nobody noticed making
from .parser import OutlineParser, split_heading
from .report import OutlineReport
```

```python
# ✅ Good — the package states what it offers, and `split_heading` is visibly
# internal despite being imported here
from .parser import OutlineParser, split_heading
from .report import OutlineReport

__all__ = ['OutlineParser', 'OutlineReport']
```

`__all__` is a list of string literals, one name per entry, in the order a reader would want to meet them —
not a computed expression.

## 5. `__init__.py` Re-Exports, and Import-Time Side Effects Name Their Reason

A package's `__init__.py` contains imports, `__all__`, and package docstring. Logic lives in a module beside
it. Where an import-time side effect is genuinely required — registering implementations into a registry so
that discovery works without the caller naming every module — a comment at that spot says what it is for.

Importing a package should be free and total. Anything that runs at import runs before the caller has
configured anything, cannot be caught selectively (it surfaces as an `ImportError` from an unrelated line), and
turns an import into something with an ordering requirement.

```python
# ❌ Bad — importing the package reads every schema off disk. A consumer that only
# wanted a Finding dataclass now fails at import time when one schema file is
# malformed, and no try/except at the call site can reach it
from .loader import SchemaLoader

_DEFAULT_SCHEMAS = SchemaLoader(SchemaConfig())
_DEFAULT_SCHEMAS.load_all()
```

```python
# ✅ Good — the only side effect is registration, and it says so
# Importing each checker module is what populates the checker registry; the discovery
# API resolves by rule id, so nothing else imports these modules.
from .frontmatter import FrontmatterChecker
from .outline import OutlineChecker

__all__ = ['FrontmatterChecker', 'OutlineChecker']
```

## 6. Optional Dependencies Degrade at Import, Raise at Construction

An implementation backed by an optional dependency is handled in two places, and the two behave differently on
purpose:

- **The package `__init__.py`** wraps the import in `try`/`except ImportError` and binds the symbol to `None`.
  Importing the library never fails because one optional backend is absent.
- **The implementation module** raises `ImportError('<pkg> package required. Install with: pip install <pkg>')`
  at **construction**, not at import.

The split puts the failure where the user can act on it. A hard import in `__init__.py` means installing the
library without the schema-validation extra breaks every unrelated import; a silent `None` with no
construction-time check means the user gets `TypeError: 'NoneType' object is not callable` and has to guess.
The message names the package and the command.

```python
# ❌ Bad — in the package __init__. Nobody can import anything from this package
# without the optional validator installed, including the pure Finding records
from .json_schema import JsonSchemaValidator
```

```python
# ✅ Good — in the package __init__: absent backend degrades to None, and the export
# list still names it so the failure is about a value, not a missing attribute
try:
    from .json_schema import JsonSchemaValidator
except ImportError:
    JsonSchemaValidator = None

__all__ = ['JsonSchemaValidator']
```

```python
# ✅ Good — in the implementation module: the module imports fine, and the user who
# actually reaches for schema validation gets a sentence they can act on
try:
    import jsonschema
except ImportError:
    jsonschema = None


class JsonSchemaValidator(FrontmatterValidator[JsonSchemaConfig]):
    def __init__(self, config: JsonSchemaConfig) -> None:
        if jsonschema is None:
            raise ImportError('jsonschema package required. Install with: pip install jsonschema')
        super().__init__(config)
```

## 7. A Suppression Names the Rule and the Reason

Every suppression is `# noqa: RULE — reason`. A bare `# noqa` does not appear.

A bare suppression silences every rule on that line, including ones introduced later by a config change or
written into the line by a subsequent edit, and it leaves no record of what was being allowed. The rule code
bounds what is silenced; the reason is what lets the next reader decide whether it still holds.

```python
# ❌ Bad — silences everything on the line forever, and says nothing about why
from .outline import OutlineChecker  # noqa
```

```python
# ✅ Good — one rule, and a reason a reviewer can check against the file
from .outline import OutlineChecker  # noqa: F401 — re-exported as package surface
```

**A `noqa` naming a rule that is not in the select list is dead and must be deleted.** Ruff's select list is
`E`, `F`, `I`, `B`; a `# noqa: UP007` or `# noqa: TRY400` suppresses nothing, because nothing was going to
fire. It is worse than no comment: it tells a reader the line was reviewed against a rule that has never run
here, so a genuine violation of the same kind elsewhere looks like an oversight rather than the norm.

```python
# ❌ Bad — UP006 is not selected, so this suppresses nothing. It reads as "we know, it
# is deliberate", which is exactly the impression the line should not give
def check_all(documents: List[Document]) -> None:  # noqa: UP006 — legacy signature
    ...
```

## 8. Import Ordering Is Ruff's

Grouping (standard library, third party, first party), alphabetization, and the blank lines between groups are
produced by ruff `I` and are not a review topic. Run `just check-fix`; do not reorder imports by hand and do
not restate isort's rules here.

## Checklist

Before committing code, verify:

- [ ] No `x.py` sits beside an `x/` package in the same directory
- [ ] Imports inside `src/` of the library's own code are relative; imports in `tests/` name `lorecraft.`
      absolutely
- [ ] No relative import uses three or more dots
- [ ] Every package `__init__.py` that re-exports declares `__all__` as a list of string literals matching
      exactly what it re-exports
- [ ] `__init__.py` contains only a docstring, imports, and `__all__`; any import-time side effect carries a
      comment naming its purpose
- [ ] An optional backend is `None`-guarded in `__init__.py` and raises
      `ImportError('<pkg> package required. Install with: pip install <pkg>')` in the constructor
- [ ] Every `# noqa` names a rule code and a reason after an em dash, and no `noqa` names a rule outside
      `E`, `F`, `I`, `B`
- [ ] Imports are in ruff's order because the formatter put them there, not because they were hand-sorted

## References

- [principle-information-hiding](principle-information-hiding.md) - Foundation: Why a package declares a
  surface rather than exposing whatever is bound
- [principle-single-responsibility](principle-single-responsibility.md) - Foundation: One name, one unit, one
  reason to change
- [python-typing](python-typing.md) - Related: The `TYPE_CHECKING` import block and its quoted annotations
- [python-naming](python-naming.md) - Related: Casing and the leading-underscore privacy marker for the
  symbols a package exports
- [python-exceptions](python-exceptions.md) - Related: Owns exception selection and inheritance
- [pattern-registry](pattern-registry.md) - Related: The discovery mechanism that import-time registration
  serves

## External References

- [Python Reference - The import system](https://docs.python.org/3/reference/import.html)
- [Ruff - isort (`I`) rules](https://docs.astral.sh/ruff/rules/#isort-i)
