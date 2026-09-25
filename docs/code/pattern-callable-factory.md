---
name: "pattern-callable-factory"
description: "Pass a class or a plain callable where a component must construct objects later or repeatedly. Load when a component builds fresh instances whose type or configuration the caller chooses, or when a factory class hierarchy, a prototype to copy, or a builder is being proposed"
type: "core"
scope: "global"
---

# Callable Factory (Deferred Construction)

## Rule

When a component must construct objects itself, later or once per unit of work, and the caller decides which
type or configuration, accept a typed callable that returns the object. In Python a class is already a callable
that constructs instances, so pass the class itself when its constructor fits the call. When configuration must
be bound in advance, pass `functools.partial(SomeClass, option=value)` or a small named function.

Type the parameter with the narrowest callable it calls: `Callable[[TextIO], ReportWriter]`, not
`Callable[..., Any]`. The component calls it with only the arguments it owns; everything else is bound by the
caller.

This single idiom replaces several catalog patterns that exist to work around languages without first-class
classes: Abstract Factory, Factory Method and Prototype. Do not write a hierarchy of one-method factory
classes, a subclass that exists only to override a `create` method, or an instance kept around to be copied.
Keyword arguments and dataclass defaults cover the ordinary Builder case; a separate builder is warranted only
for multistep assembly with ordering or validation between the steps.

When the component needs an already-built collaborator rather than the ability to build more of them, inject
the instance instead ([pattern-dependency-injection](pattern-dependency-injection.md)).

## Examples

1. **A factory hierarchy where a class would do**
   A check run opens one report writer per output stream; the caller picks the format.

```python
# ❌ Bad — two classes and an abstract base exist only to call a constructor.
class WriterFactory(ABC):
    @abstractmethod
    def create(self, stream: TextIO) -> ReportWriter: ...


class JsonWriterFactory(WriterFactory):
    def create(self, stream: TextIO) -> ReportWriter:
        return JsonReportWriter(stream)


def report(findings: list[Finding], stream: TextIO, factory: WriterFactory) -> None:
    factory.create(stream).write(findings)
```

```python
# ✅ Good — the class is the factory; the caller passes it directly.
def report(
    findings: list[Finding],
    stream: TextIO,
    make_writer: Callable[[TextIO], ReportWriter],
) -> None:
    make_writer(stream).write(findings)


report(findings, sys.stdout, JsonReportWriter)
```

2. **Binding configuration the component does not own**
   The text writer takes a colour option the report function knows nothing about.

```python
# ❌ Bad — the report function grows a parameter for every option of every writer.
def report(findings: list[Finding], stream: TextIO, fmt: str, colour: bool) -> None:
    writer = TextReportWriter(stream, colour=colour) if fmt == 'text' else JsonReportWriter(stream)
    writer.write(findings)
```

```python
# ✅ Good — the caller binds the option; the report function stays unchanged.
report(findings, sys.stdout, partial(TextReportWriter, colour=False))
```

## Why It Matters

A callable parameter keeps construction policy with the caller who knows it, without an interface hierarchy
that doubles the class count. The component's signature states exactly which arguments it supplies. Tests pass
a stub class, and a new product type needs no new factory class.

## Pragmatism Caveat

If the component constructs one object once, let the caller construct it and pass the instance. If there is one
product type and no caller varies it, call the constructor directly. Keep a named function over `partial` when
binding needs logic or several steps.

## Checklist

- [ ] Deferred or repeated construction takes a typed callable, not a factory object
- [ ] A class is passed directly when its constructor matches the call
- [ ] Configuration the component does not own is bound by the caller with `partial` or a named function
- [ ] The callable's type names its exact arguments and return type
- [ ] No abstract factory, factory-method subclass or prototype instance is introduced
- [ ] A builder exists only for multistep assembly with ordering or validation

## References

- [pattern-dependency-injection](pattern-dependency-injection.md) - Related: Inject an instance when no later construction is needed
- [pattern-protocol](pattern-protocol.md) - Related: Types the product the factory returns when several exist
- [python-typing](python-typing.md) - Related: Owns the spelling of `Callable` annotations

## External References

- [Python Patterns Guide — Abstract Factory](https://python-patterns.guide/gang-of-four/abstract-factory/)
- [Python Patterns Guide — Factory Method](https://python-patterns.guide/gang-of-four/factory-method/)
- [Python Patterns Guide — Prototype](https://python-patterns.guide/gang-of-four/prototype/)
- [Python docs — `functools.partial`](https://docs.python.org/3.12/library/functools.html#functools.partial)
