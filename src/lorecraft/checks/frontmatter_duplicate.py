"""Where a frontmatter key written twice is reported: each later occurrence, pointing back at the first.

YAML lets a mapping repeat a key, and the decoder keeps the value of its last occurrence without a word, so a
field can be written twice and read as whichever was written second. That is a finding whether the two values
are equal or differ: one of the two lines says nothing the document means.

The frontmatter check and the skill check read the same `Frontmatter` value, so both report a repeated key the
same way; only the rule differs, `frontmatter.duplicate-key` or `skill.duplicate-key`. Only top-level keys
written as strings are compared, the keys `Frontmatter.keys` lists.
"""

from lorecraft.project.syntax import Frontmatter, LineNumber

from .reporting import Violation


def duplicate_key_violations(frontmatter: Frontmatter, *, rule: str) -> tuple[Violation, ...]:
    """One violation per occurrence of a top-level key after its first, on its own line. Pure: raises nothing.

    Each names the line of the key's first occurrence, so the third occurrence of a key points back at the first,
    not at the second. The key is printed as its `repr`, as the name and schema messages print a value: it is
    the key as decoded, so a key holding a newline would otherwise split the finding over two lines, one holding a
    lone surrogate could not be written to the terminal at all, and an escape sequence would vanish into the
    character it stands for.

    Args:
        frontmatter: The decoded frontmatter whose top-level keys are compared; read, never changed.
        rule: The identifier every violation is reported under, which names the check that reports it.
    """
    first_lines: dict[str, LineNumber] = {}
    violations: list[Violation] = []
    for key in frontmatter.keys:
        if key.name in first_lines:
            first_line = first_lines[key.name]
            violations.append(
                Violation(line=key.line, rule=rule, message=f'{key.name!r} is already written on line {first_line}')
            )
        else:
            first_lines[key.name] = key.line
    return tuple(violations)
