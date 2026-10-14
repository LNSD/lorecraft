"""Fail on a reST double-backtick literal in a docstring.

`docs/code/python-docstrings.md` §1 writes docstring prose in Markdown, so a code literal is a single-backtick
span. Ruff has no rule for the reST spelling, so `just check` runs this script over `src`, `gen`, `scripts` and
`tests`, or over the paths it is given. Fenced blocks are skipped: a line of three backticks opens or closes one,
and what is inside is code or sample output, where two backticks may be part of the example.

Only docstrings are read: the module's, each class's and each function's, and the string that follows an
assignment or type alias in a module or class body, which documents the attribute. A comment or a string that
is not a docstring is left alone.

Exit status is 0 when no docstring holds one, and 1 when any does, each reported as `path:line`.
"""

import ast
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Final

_DEFAULT_PATHS: Final[tuple[str, ...]] = ('src', 'gen', 'scripts', 'tests')

_FENCE: Final[str] = '```'

# Exactly two backticks: a run of three or more is a fence, not a literal.
_DOUBLE_BACKTICK: Final[re.Pattern[str]] = re.compile(r'(?<!`)``(?!`)')

_HINT: Final[str] = 'double-backtick literal in a docstring; use single backticks'


def find_double_backticks(source: str) -> list[int]:
    """List the lines of `source` where a docstring holds a double-backtick literal.

    The lines are read as written, not as the string they evaluate to, so an escape sequence or a backslash before
    a line break in a docstring does not move the line reported.

    Args:
        source: The text of one Python module.

    Returns:
        The 1-based line numbers, in order.
    """
    # Not `splitlines`, which also breaks on a form feed and other separators that `ast` counts as text.
    source_lines = source.split('\n')
    hits: list[int] = []
    for docstring in _docstrings(ast.parse(source)):
        in_fence = False
        first_line = docstring.lineno
        last_line = docstring.end_lineno or first_line
        for number in range(first_line, last_line + 1):
            # The string's own columns, so a comment after its closing quotes is not read as part of it. `ast`
            # counts columns in UTF-8 bytes.
            written = source_lines[number - 1].encode()
            if number == last_line:
                written = written[: docstring.end_col_offset]
            if number == first_line:
                written = written[docstring.col_offset :]
            text = written.decode()
            if text.strip().startswith(_FENCE):
                in_fence = not in_fence
            elif not in_fence and _DOUBLE_BACKTICK.search(text):
                hits.append(number)
    return hits


def _docstrings(tree: ast.Module) -> Iterator[ast.Constant]:
    """Yield the string node of each docstring in the module.

    Args:
        tree: The parsed module, walked whole.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if node.body and (docstring := _string_of(node.body[0])):
            yield docstring
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        # An attribute's docstring is the string statement right after its assignment.
        for assignment, following in zip(node.body, node.body[1:], strict=False):
            if isinstance(assignment, ast.Assign | ast.AnnAssign | ast.TypeAlias) and (
                docstring := _string_of(following)
            ):
                yield docstring


def _string_of(statement: ast.stmt) -> ast.Constant | None:
    """Return the string constant a statement is made of, or `None` when it is anything else.

    Args:
        statement: One statement of a module, class or function body.
    """
    if (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    ):
        return statement.value
    return None


def _python_files(paths: list[str]) -> Iterator[Path]:
    """Yield every `.py` file under the given files and directories, in path order.

    Args:
        paths: Files and directories; one that does not exist is passed through and fails when it is read.
    """
    for name in paths:
        path = Path(name)
        if path.is_dir():
            yield from sorted(path.rglob('*.py'))
        else:
            yield path


def main(argv: list[str]) -> int:
    """Report each double-backtick literal as `path:line: hint`, and return the exit status.

    Args:
        argv: The files and directories to read, without the program name; the default roots when empty.
    """
    hits = 0
    for path in _python_files(argv or list(_DEFAULT_PATHS)):
        for line in find_double_backticks(path.read_text(encoding='utf-8')):
            print(f'{path}:{line}: {_HINT}')
            hits += 1
    return 1 if hits else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
