---
name: "python-literals"
description: "Multi-line string literals written as one `textwrap.dedent` literal that opens with `\"\"\"\\`, is indented with the code around it and is bound to a name before it is used, never glued from `\\n`-joined pieces or implicit concatenation, and where a literal stays inline: a docstring, a string of one line, a value `dedent` cannot hold, an escape the fixture is about. Load when writing a string that spans several lines, a YAML, Markdown or text fixture in a test, or a block of expected output"
type: "core"
scope: "global"
---

# Multi-Line String Literals

**A string of several lines is written as the lines it holds.** A reader sees the text as it will be, in the
place it is used, indented with the code around it, and `textwrap.dedent` takes the code's indentation off. It is
the form `indoc!` gives a Rust raw string.

Docstrings are owned by [python-docstrings](python-docstrings.md). The shape of a test that holds such a
fixture is owned by [tests-functions](tests-functions.md). This document is about the literal itself.

## 1. A Multi-Line String Is One Dedented Literal

A string with two or more lines of content is one triple-quoted literal passed to `textwrap.dedent`, indented one
level past the statement that holds it. The text reads top to bottom as it is, and the quotes and the call are
the only things around it.

The reason is that a reader has to rebuild a glued string in their head, find where each `\n` falls and what
sits between two pieces, before they know what the text is. A literal shows it at once, and a diff of it shows
the changed line.

```python
# ❌ Bad — the reader joins five pieces and counts the `\n`s to see a four-line block
block = 'name: guide\n' + 'tags:\n' + '  - a\n' + '  - b\n'
```

```python
# ❌ Bad — implicit concatenation; one missing `\n` fuses two lines and nothing looks wrong
block = (
    'name: guide\n'
    'tags:\n'
    '  - a\n'
    '  - b\n'
)
```

```python
# ✅ Good — the block as it will be, indented with the code around it
block = dedent("""\
    name: guide
    tags:
      - a
      - b
    """)
```

`dedent` removes the whitespace every line shares, so a line indented further than the others keeps the
difference, as `  - a` does above. It is imported as `from textwrap import dedent`.

A multi-line string that does not follow this rule is converted when its statement is touched, as the other
literal and docstring forms are. Code the change does not touch is left as it is.

## 2. Open With `"""\` and Close on Its Own Line

The opening quotes are followed by a backslash and the text starts on the next line, so the first line is
indented like every other and the value does not begin with a line break. The closing quotes stand on their own
line, at the indentation of the statement or one level in, and the string ends with the line break before
them.

A trailing newline is kept: the closing quotes on their own line write it, and a block of YAML, Markdown or
expected output is a text file that ends with a line break. A value that must not end with one closes on its
last line of text, `text""")`, so what the string ends with is read where it ends.

The split form, `dedent(` then `"""\` then the text then `"""` and `)` each on a line, is the same literal laid
out over more lines, and `ruff format` leaves it as it is.

```python
# ❌ Bad — the first line starts at the quotes and is out of line with the rest, and `dedent` finds
# no margin common to all the lines, so it removes nothing
block = dedent("""name: guide
    tags: [a, b]
    """)
```

```python
# ❌ Bad — with no backslash the value opens with a line break, so a block that starts at its first
# line is not what the literal says
block = dedent("""
    name: guide
    tags: [a, b]
    """)
```

```python
# ✅ Good — every line shares one margin, and the string ends with a line break
block = dedent("""\
    name: guide
    tags: [a, b]
    """)
```

```python
# ✅ Good — no final line break is wanted, so the text closes the literal
title = dedent("""\
    first line
    second line""")
```

## 3. Bind the Literal to a Name Before It Is Used

A dedented literal is bound to a name in a statement of its own, and the name is what is passed on. It is never
written as an argument of a constructor, a function call or a container literal: `dedent(...)` is the only call
it sits in.

The reason is that a block of text in the middle of a call splits its arguments. A reader has to read past the
whole block to find what the arguments after it are, and the call's own layout reflows around the text.

```python
# ❌ Bad — the call's arguments are split by a block of text, and `body=` is the whole of the call
skill = Skill(
    'review',
    body=dedent("""\
        # Review

        Read [the steps](/steps.md).
        """),
)
```

```python
# ✅ Good — the text is one statement, and the call reads in one line
body = dedent("""\
    # Review

    Read [the steps](/steps.md).
    """)
skill = Skill('review', body=body)
```

## 4. A Literal Stays Inline Where It Cannot Be Dedented or Reads Better as One Line

These stay as they are, so the value is what the code says:

- **A docstring.** It is documentation and is owned by [python-docstrings](python-docstrings.md).
- **A string with one line of content**, with or without a final `\n`, such as `'name: guide\n'`. It is
  already readable on one line, and a literal of three lines for it says nothing more. Two lines of content,
  such as `'title\nbody'`, are a multi-line string and follow the rule.
- **A value `dedent` cannot hold.** A value with a line made only of spaces or tabs, or whose every line starts
  with whitespace, cannot be written in the dedented form, because `dedent` removes that whitespace: a
  whitespace-only line becomes an empty one, and a margin every line shares is taken off.
- **A fixture about one escape**, such as `\t`, `\r\n` or a control character. The escape survives inside a
  dedented literal, but a fixture whose subject is that one character reads best on one line, where the escape
  is the only thing in it.

A value that spans lines and is joined with fixed lines is built from two parts, each bound to a name, not one
f-string: the fixed lines are dedented, and the value is added after, by interpolating into the result or by
joining outside the literal. A multi-line value interpolated into the literal carries its own margin, which `dedent` then does not
remove.

```python
# ✅ Good — the line of two spaces is the fixture, and `dedent` would empty it
block = 'a: |\n  \n    text\n'
```

```python
# ✅ Good — a tab is the thing under test, and one line with the escape says so
block = 'a:\n\tb: 1\n'
```

```python
# ✅ Good — the fixed lines are dedented, and the multi-line value is joined after
header = dedent("""\
    name: guide
    notes: |
    """)
block = header + indented_notes
```

## Checklist

Before committing code, verify:

- [ ] A string of two or more lines of content is one `dedent("""\ ...""")` literal, not `+`, an implicit
      concatenation or `'\n'.join(...)` of pieces
- [ ] The opening quotes are followed by a backslash, the text starts on the next line, and every line of the
      literal shares the margin the code gives it
- [ ] The closing quotes stand on their own line, and a value that must not end with a line break closes on its
      last line of text
- [ ] A multi-line literal is bound to a name before it is used; it never appears inside another call
- [ ] A docstring, a string with one line of content, a value with a whitespace-only line or whose every line
      starts with whitespace, and a fixture about one escape are left inline
- [ ] A multi-line value is joined to dedented fixed lines after `dedent`, never interpolated into the literal

## References

- [python-docstrings](python-docstrings.md) - Related: Owns the docstring, which is outside this rule
- [tests-functions](tests-functions.md) - Related: Owns the shape of a test, whose Given block holds the fixtures
  this rule writes

## External References

- [Python docs — `textwrap.dedent`](https://docs.python.org/3/library/textwrap.html#textwrap.dedent)
- [`indoc` — indented document literals for Rust](https://docs.rs/indoc/latest/indoc/)
