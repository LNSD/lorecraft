---
name: "pattern-registry"
description: "Registry: implementations join by registering a name and declaring capabilities as class data, instead of by editing a dispatcher. Load when adding a branch to an if/elif chain over a type string, when a new implementation requires editing a central factory, or when a caller must know what an implementation supports before dispatching"
type: "core"
scope: "global"
---

# Registry (Name-Keyed Extension Seam)

## Rule

When a family of implementations is selected at runtime by a name that comes from configuration, a request, or
a CLI flag, the selection must be a **lookup in a mapping**, not a chain of branches in a dispatcher. An
implementation joins the family by **registering a name**; it never joins by having a branch added for it
somewhere else.

Six rules:

1. **Implementations register; dispatchers do not branch.** A new implementation adds a `register(name, cls)`
   call next to itself. It does not add an `elif` to a function that has to be found, read, and edited — a file
   that grows one branch per implementation and must be touched by every contributor.
2. **The registry key is data, not a branch.** The name is a value looked up in a dict. Because it is data, the
   set of valid names can be listed, logged, validated against, and shown in an error message. A chain of
   `elif`s can do none of those.
3. **Capability is declared as data on the class, so a caller can ask before it dispatches.** Whether an
   implementation can rewrite a document in place, which check modes it accepts, whether its edits can be
   staged and applied as one unit — these are class attributes (`SUPPORTED_MODES`, `SUPPORTS_ATOMIC_FIX`),
   read off the registered class before it is constructed. The alternative is constructing it, calling it, and
   catching the failure, which is a runtime check for a fact that was known statically.
4. **Discovery over a package is lazy and idempotent.** Walking the implementations package with
   `pkgutil.iter_modules` and importing each module runs once, on first use, and running it a second time
   changes nothing. Import at module-import time and the registry's contents depend on import order; re-import
   without a guard and registrations are duplicated or clobbered.
5. **An unknown name fails loudly, listing the known names.** `KeyError: 'frontmater'` is not a diagnosis. The
   error must say what was asked for and what was available, because the overwhelmingly common cause is a typo
   in a config file and the fix is visible the moment both are printed side by side.
6. **Discovery that swallows import errors must log them.** An implementation whose module fails to import — a
   missing optional dependency, a syntax error in a rarely exercised file — disappears from the registry. If
   discovery catches `ImportError` and continues silently, the symptom is "unknown name" for a name that is
   spelled correctly and whose file is right there. This is the worst failure mode this pattern has, and the
   only defence is a warning log naming the module and the exception.

## Examples

1. **A dispatcher that must be edited for every new implementation**
   The factory branches on a type string, so adding a check means editing a central function that every
   contributor touches and that grows without bound.

```python
# ❌ Bad — every new check edits this function. Two contributors adding checks in the same
# week conflict here and nowhere else, and the branch for a checker nobody imported raises
# NameError at dispatch time rather than at import time.
def build_checker(kind: str, config: dict[str, Any]) -> Checker:
    if kind == 'frontmatter':
        return FrontmatterChecker(config)
    elif kind == 'outline':
        return OutlineChecker(config)
    elif kind == 'budget':
        return BudgetChecker(config)
    else:
        raise ValueError(f'unknown checker kind: {kind}')
```

```python
# ✅ Good — the dispatcher never changes. A check joins by registering its name beside its
# own definition, so adding one touches exactly one file.
class CheckerRegistry:
    """Maps a check name to the class that implements it."""

    def __init__(self) -> None:
        self._entries: dict[str, type[Checker]] = {}

    def register(self, name: str, checker_cls: type[Checker]) -> None:
        """Register `checker_cls` under `name`.

        Raises:
            DuplicateCheckerError: If `name` is already registered to a different class.
        """
        existing = self._entries.get(name)
        if existing is not None and existing is not checker_cls:
            raise DuplicateCheckerError(f'{name!r} already registered to {existing.__name__}')
        self._entries[name] = checker_cls
        logger.debug(f'registered checker {name!r} -> {checker_cls.__name__}')

    def get(self, name: str) -> type[Checker]:
        """Look up a registered checker class.

        Raises:
            UnknownCheckerError: If `name` is not registered.
        """
        try:
            return self._entries[name]
        except KeyError as exc:
            known = ', '.join(sorted(self._entries))
            raise UnknownCheckerError(f'unknown checker {name!r}; known checkers: {known}') from exc


registry = CheckerRegistry()
registry.register('frontmatter', FrontmatterChecker)
```

2. **Capability discovered by failing, instead of declared as data**
   The caller cannot tell whether a checker can stage its edits and apply them to a whole corpus as one unit,
   so it tries and interprets the exception.

```python
# ❌ Bad — capability is inferred from a raised exception. The `except` also swallows genuine
# rewrite failures (an unparsable document, a read-only file), so a real error is silently
# retried as an unstaged rewrite and the corpus is left half-fixed with no record of why.
def apply_fixes(checker: Checker, documents: list[Document]) -> None:
    try:
        checker.begin_fix()
        for document in documents:
            checker.fix(document)
        checker.commit_fix()
    except Exception:
        for document in documents:
            checker.fix(document)
```

```python
# ✅ Good — capability is a class attribute, read before dispatching. The caller chooses a
# strategy from data, and a genuine rewrite failure still propagates.
class FrontmatterChecker(Checker):
    """Checks a document's frontmatter against the schema declared for its corpus."""

    SUPPORTED_MODES: frozenset[CheckMode] = frozenset({CheckMode.REPORT})
    SUPPORTS_ATOMIC_FIX: bool = False


def apply_fixes(checker: Checker, documents: list[Document], mode: CheckMode) -> None:
    """Run a checker over a corpus, staging the edits only where the checker can stage them.

    Raises:
        UnsupportedModeError: If the checker does not support `mode`.
    """
    if mode not in type(checker).SUPPORTED_MODES:
        supported = ', '.join(sorted(m.value for m in type(checker).SUPPORTED_MODES))
        raise UnsupportedModeError(f'{type(checker).__name__} supports: {supported}, not {mode.value}')

    if not type(checker).SUPPORTS_ATOMIC_FIX:
        for document in documents:
            checker.fix(document)
        return

    checker.begin_fix()
    for document in documents:
        checker.fix(document)
    checker.commit_fix()
```

3. **Discovery that hides the reason an implementation is missing**
   Auto-discovery walks the checkers package. Catching import errors without logging them turns a missing
   optional dependency into an unexplained "unknown name".

```python
# ❌ Bad — the schema-validation library one checker needs is not installed, its module
# raises ImportError, and the registry silently comes up one entry short. The author sees
# "unknown checker 'skill-spec'" for a name spelled exactly as the format specification
# documents it, and nothing anywhere names the missing package.
def discover() -> None:
    for module_info in pkgutil.iter_modules(checkers.__path__):
        try:
            importlib.import_module(f'{checkers.__name__}.{module_info.name}')
        except ImportError:
            pass
```

```python
# ✅ Good — discovery runs once, tolerates a missing optional dependency, and says exactly
# which module failed and why, so "unknown checker" is always traceable to a logged cause.
_discovered = False


def discover() -> None:
    """Import every checker module once, registering what imports successfully.

    Modules that fail to import are logged and skipped: an optional dependency may be absent.
    Safe to call repeatedly; subsequent calls are no-ops.
    """
    global _discovered
    if _discovered:
        return

    for module_info in pkgutil.iter_modules(checkers.__path__):
        module_name = f'{checkers.__name__}.{module_info.name}'
        try:
            importlib.import_module(module_name)
        except ImportError as exc:
            logger.warning(f'skipping checker module {module_name}: {exc}')

    _discovered = True
```

4. **Construction that hides which name failed**
   The factory looks up and constructs in one step, so a configuration failure inside the implementation is
   reported without the name that selected it.

```python
# ❌ Bad — the checker's own schema-loading error propagates with no mention of the registry
# name from the format specification, so the author reading the traceback cannot tell which
# of four configured checks is misconfigured.
def build(name: str, config: dict[str, Any]) -> Checker:
    return registry.get(name)(**config)
```

```python
# ✅ Good — lookup and construction are separate, and a construction failure is re-raised
# carrying the registry name that selected the implementation.
def build(name: str, config: dict[str, Any]) -> Checker:
    """Construct the checker registered under `name`.

    Raises:
        UnknownCheckerError: If `name` is not registered.
        CheckerConfigError: If the registered checker rejects `config`.
    """
    discover()
    checker_cls = registry.get(name)
    try:
        return checker_cls(**config)
    except TypeError as exc:
        raise CheckerConfigError(f'invalid configuration for checker {name!r}: {exc}') from exc
```

## Why It Matters

**A dispatcher that grows a branch per implementation is a file every contributor edits.** It is the merge
conflict that appears in every parallel feature branch, and the one place where forgetting a line makes a
correctly written implementation invisible. A registry moves that line next to the implementation, where the
person adding it is already looking. The dispatcher stays closed to modification while the family stays open
to extension.

**A key that is data can be validated, listed, and explained.** The set of registered names can be printed in a
`--help`, checked against a format specification before any document is read, and — most importantly —
included in the error raised for an unrecognised one. A typo in a configuration file becomes a one-line fix
instead of an investigation.

**Capability declared as data lets a caller decide instead of discover.** Reading `SUPPORTS_ATOMIC_FIX` off
the class costs nothing and happens before any document is opened. Learning the same fact from an exception
costs a failed attempt, requires a broad `except` that also swallows real failures, and leaves the corpus
half-rewritten.

**Silent discovery failures are the pattern's characteristic bug.** Every other failure mode here announces
itself. A swallowed `ImportError` produces a registry that is quietly incomplete, and the resulting error names
the wrong thing entirely: the name the author typed correctly, rather than the package that is not installed.
A single warning log is the difference between a five-minute fix and a day of confusion.

## Pragmatism Caveat

A registry buys extensibility by adding indirection: the path from a name to the code that runs it goes through
a mapping and, with discovery, through an import walk. That is worth paying for an open family and not
otherwise:

- **A closed set that will not grow does not need one.** Two implementations chosen by a boolean, or a fixed
  enum of three strategies that ship together and change together, are clearer as a direct `match` or a
  module-level dict literal. The seam exists for implementations added later, by someone else.
- **A family entirely under one module's control does not need auto-discovery.** Explicit imports with explicit
  `register` calls in one `__init__` are easier to follow than a package walk, and they fail at import time
  rather than at first lookup. Add discovery when implementations are optional or dependency-gated.
- **Do not register something that is selected at import time anyway.** If the caller already names the class
  directly, a registry adds a string that can be misspelled in exchange for nothing.
- **A registry does not replace a shared interface.** Registered classes must still satisfy one contract; the
  mapping only chooses between them. Registering unrelated types under one namespace moves the `elif` chain
  into the caller.

Deviating is legitimate when one of these cases applies and the reason is written at the spot. **An
undocumented deviation is always wrong** — a hand-rolled branch beside a registry, or a discovery loop with a
bare `except`, is indistinguishable from an oversight, and review must treat it as one.

## Checklist

- [ ] A new implementation joins by registering a name beside itself, editing no central dispatcher
- [ ] The selection is a lookup in a mapping, not an `if` / `elif` chain over a name
- [ ] Lookup failure raises a domain exception that names the requested key and lists the known keys
- [ ] Capabilities are class attributes read before dispatch, not facts discovered by catching an exception
- [ ] Auto-discovery runs once and is a no-op on subsequent calls
- [ ] Discovery logs every module it skips, with the module name and the exception
- [ ] Discovery never uses a bare `except`; it catches the specific error an absent optional dependency raises
- [ ] Registering a name already bound to a different class is an error, not a silent overwrite
- [ ] Construction failures are re-raised carrying the registry name that selected the implementation
- [ ] No registry was added for a closed set of implementations that ship and change together

## References

- [principle-information-hiding](principle-information-hiding.md) - Foundation: Callers depend on the registered contract, never on which class was selected
- [principle-least-surprise](principle-least-surprise.md) - Foundation: An unknown name that lists the known names is diagnosable at a glance
- [pattern-value-object](pattern-value-object.md) - Related: A registry key is an identity, and so a candidate for a value object
- [pattern-resource-lifecycle](pattern-resource-lifecycle.md) - Related: The registry hands back a class; the caller owns the instance's lifecycle

## External References

- [Python docs — `pkgutil.iter_modules`](https://docs.python.org/3/library/pkgutil.html#pkgutil.iter_modules)
- [Python Packaging — Creating and Discovering Plugins](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/)
- [Martin Fowler — Registry](https://martinfowler.com/eaaCatalog/registry.html)
