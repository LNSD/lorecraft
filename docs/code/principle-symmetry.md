---
name: "principle-symmetry"
description: "Symmetry — express the same idea the same way; split near-duplicates into identical parts and clearly different parts, one altitude per body. Load when writing something that resembles existing code, or reviewing sibling functions, branches, or modules"
type: "principle"
scope: "global"
---

# Symmetry (Express the Same Idea the Same Way)

## Rule

The same idea is expressed the same way everywhere it appears. Two pieces of code that are almost the same
are split so the identical parts are literally identical and the differing parts are the only visible
difference.

1. **One idea, one shape.** Two functions answering the same question take parameters in the same order,
   return the same shape, and name their steps the same way. Two values playing the same role expose the same
   entry point, so a caller holds either one the same way.
2. **Near-duplicates keep an identical skeleton.** Same step order, local names, and error handling. Only
   the lines that must diverge differ.
3. **One level of abstraction per function.** Every statement in a body sits at the same altitude.
4. **Sibling branches carry comparable weight.** Arms and branches of one construct all delegate, or all
   inline.
5. **Paired operations stay paired.** Parse and render, connect and disconnect, register and look up sit in
   the same module, at the same level, in the same vocabulary. `principle-least-surprise` owns the inverse's
   name.
6. **Sibling modules in the same role share a layout.** They expose the same entry points in the same file
   positions.

Symmetry is not deduplication. Two symmetric copies with one visible difference are a good outcome: whether
they are one fact worth extracting is a separate decision, and symmetry is what makes it easy to take.

## Examples

1. **One idea, one shape**
   Three lookups that answer the same question about the workspace model: what is at this path.

```python
# ❌ Bad — the model moves between first and last parameter, and "not there" is spelled three ways; a
# caller written against one treated a KeyError as a bug and crashed on the other two's missing paths.
def spec_for(corpus: CorpusName, model: WorkspaceModel) -> SpecRef: ...  # raises KeyError
def document_at(model: WorkspaceModel, path: RootRelativePath) -> DocumentRef | None: ...
def find_skill(path: RootRelativePath, model: WorkspaceModel) -> tuple[SkillRef, ...] | bool: ...
```

```python
# ✅ Good — model first, subject second, absence is None.
def spec_for(model: WorkspaceModel, corpus: CorpusName) -> SpecRef | None: ...
def document_at(model: WorkspaceModel, path: RootRelativePath) -> DocumentRef | None: ...
def skill_at(model: WorkspaceModel, path: RootRelativePath) -> SkillRef | None: ...
```

2. **Near-duplicates keep an identical skeleton**
   Two checks that hold a frontmatter to a schema, one for guides and one for agent prompts. They stay two
   functions.

```python
# ❌ Bad — the same steps in a different order under different names; a fix to the unparseable-block guard
# landed in one and was missed in the other for two releases.
def check_guide(schema: GuideSchema, *, header: FrontmatterNode) -> list[Occurrence]:
    if isinstance(header, MissingFrontmatter):
        return [missing('guide')]
    found = [occurrence_for(error) for error in schema.errors_in(header.data)]
    ...

def check_prompt(header: FrontmatterNode, schema: PromptSchema) -> list[Occurrence]:
    issues = [to_occurrence(problem) for problem in schema.problems(header.data)]
    if isinstance(header, (MissingFrontmatter, InvalidYamlFrontmatter)):
        return [missing('prompt')]
    ...
```

```python
# ✅ Good — identical skeleton; the two lines that differ are the two that must.
def check_guide(schema: GuideSchema, *, frontmatter: FrontmatterNode) -> list[Occurrence]:
    if isinstance(frontmatter, MissingFrontmatter):
        return [missing('guide')]
    return [occurrence_for('guide', problem) for problem in schema.validate(frontmatter.data)]

def check_prompt(schema: PromptSchema, *, frontmatter: FrontmatterNode) -> list[Occurrence]:
    if isinstance(frontmatter, MissingFrontmatter):
        return [missing('prompt')]
    return [occurrence_for('prompt', problem) for problem in schema.validate(frontmatter.data)]
```

3. **One altitude, comparable branches**
   A dispatch over the changes between two snapshots.

```python
# ❌ Bad — two arms state what happens and the third states how; a second index copied the short arms and
# forgot to drop the stale parse.
match change.kind:
    case ChangeKind.ADDED:
        self._index(change.path)
    case ChangeKind.MODIFIED:
        self._reindex(change.path)
    case ChangeKind.DELETED:
        self._frontmatters.pop(change.path, None)
        self._parses.pop(change.path, None)
        self._paths.remove(change.path)
    case _:
        assert_never(change.kind)
```

```python
# ✅ Good — every arm states an intention; the cleanup lives with the other transitions.
match change.kind:
    case ChangeKind.ADDED:
        self._index(change.path)
    case ChangeKind.MODIFIED:
        self._reindex(change.path)
    case ChangeKind.DELETED:
        self._forget(change.path)
    case _:
        assert_never(change.kind)
```

## Why It Matters

Asymmetry is paid on every read. A reader who has understood one member of a pair should skip the other. When
the shapes disagree, the reader reads both in full and diffs them by hand. That cost is invisible in a diff
and unbounded over a file's life.

Asymmetry is paid again in bugs. A reviewer's strongest tool is noticing that two things that should match do
not. A fix applied to one variant and missed in the other passes review because nothing looks out of place.
Mixed altitude hides effects from the call site. An unbalanced branch hides a procedure inside a case label.

Symmetry compounds. When every check exposes the same entry point in the same position, a reader lands in an
unfamiliar check already knowing where to look. That return is available only while the consistency holds
everywhere.

## Pragmatism Caveat

False symmetry is worse than asymmetry. A matching shape claims that the behavior matches, and a reader acts
on the claim. A branch is not padded to balance it. A function that cannot fail is not given an error return to
line up with its neighbor. A type that owns nothing is not given a `disconnect()`.

Symmetry is bounded by the seams around it. A library dictates its own parameter order, error shape and
wording. The foreign shape is matched at the boundary, translated there, and the project's shape used
everywhere else. Two variants diverging permanently break their symmetry on purpose, and the cheapest way is
a rename, so the reader stops expecting a pair.

Symmetry broken deliberately carries a comment at the declaration. An undocumented asymmetry is always
wrong: the next reader cannot tell it from the copy nobody updated.

## Checklist

Before committing code, verify:

- [ ] Functions answering the same question take the same parameter order and return the same shape
- [ ] Values playing the same role expose the same entry point
- [ ] Near-duplicate bodies share step order, local names, and error handling; only the intended lines differ
- [ ] No function body mixes statements that name an intention with statements that perform the mechanism
- [ ] Sibling match arms and branches all delegate or all inline; none hides a procedure
- [ ] Every parse, connect, or register has its inverse in the same module at the same level
- [ ] Modules playing the same role expose the same entry points in the same positions
- [ ] No shape was matched that the behavior does not match, and no branch was padded to balance it
- [ ] Any deliberate asymmetry carries a comment saying why

## References

- [principle-least-surprise](principle-least-surprise.md) - Related: Owns the naming contract for paired
  operations; a symmetric shape makes a name's prediction hold
- [principle-single-responsibility](principle-single-responsibility.md) - Related: A body that mixes altitudes
  is usually a function with two responsibilities

## External References

- [Symmetry, in Kent Beck's Implementation Patterns](https://blog.iterate.no/2012/06/20/programming-like-kent-beck/)
- [Mastering Programming — Kent Beck](https://tidyfirst.substack.com/p/mastering-programming)
- [The Value of Symmetry — Scott Allen](https://odetocode.com/blogs/scott/archive/2011/02/07/the-value-of-symmetry.aspx)
- [Consistency creates cognitive leverage — A Philosophy of Software Design](https://danlebrero.com/2021/02/24/philosophy-of-software-design-summary/)
- [Single Level of Abstraction Principle](https://principles-wiki.net/principles:single_level_of_abstraction)
