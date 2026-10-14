"""The docstring literal check: what it flags, what it skips and how it reports.

The check is the script `scripts/check_docstring_literals.py`, which `just check` runs over `src`, `gen`,
`scripts` and `tests`. Each case writes a small module and reads the lines it flags.
"""

from pathlib import Path
from textwrap import dedent

import pytest
from check_docstring_literals import find_double_backticks, main


@pytest.mark.it
class TestFindDoubleBackticks:
    def test_find_double_backticks_with_literal_in_module_docstring_returns_its_line(self) -> None:
        #: Given
        source = dedent('''\
            """Summary.

            Reads ``path`` as given.
            """
            ''')

        #: When
        lines = find_double_backticks(source)

        #: Then
        assert lines == [3], f'the literal on line 3 is flagged, got {lines}'

    def test_find_double_backticks_with_literals_in_class_and_function_docstrings_returns_their_lines(self) -> None:
        #: Given
        source = dedent('''\
            class Walker:
                """Walks ``root``."""

                def step(self) -> None:
                    """Takes one ``step``."""
            ''')

        #: When
        lines = find_double_backticks(source)

        #: Then
        assert lines == [2, 5], f'the class and the method docstring are both read, got {lines}'

    def test_find_double_backticks_with_literal_in_attribute_docstring_returns_its_line(self) -> None:
        #: Given
        source = dedent('''\
            LIMIT = 3
            """How many ``items``."""

            type Count = int
            """A ``count``."""


            class Settings:
                size: int = 1
                """The ``size``."""
            ''')

        #: When
        lines = find_double_backticks(source)

        #: Then
        assert lines == [2, 5, 10], f'a string after an assignment or a type alias is read, got {lines}'

    def test_find_double_backticks_with_form_feed_before_literal_returns_its_written_line(self) -> None:
        #: Given
        source = dedent('''\
            def f() -> None:
                """Summary.\x0cStill the first line.

                Reads ``path``.
                """
            ''')

        #: When
        lines = find_double_backticks(source)

        #: Then
        assert lines == [4], f'a form feed is not a line break, got {lines}'

    def test_find_double_backticks_with_literal_in_comment_after_docstring_returns_nothing(self) -> None:
        #: Given
        source = dedent('''\
            def f() -> None:
                """Summary."""  # Not ``this``.
            ''')

        #: When
        lines = find_double_backticks(source)

        #: Then
        assert lines == [], f'a comment after the closing quotes is not part of the docstring, got {lines}'

    def test_find_double_backticks_with_literals_on_several_lines_returns_each_line(self) -> None:
        #: Given
        source = dedent('''\
            def f() -> None:
                """Summary.

                First ``a``.
                No literal.
                Last ``b``.
                """
            ''')

        #: When
        lines = find_double_backticks(source)

        #: Then
        assert lines == [4, 6], f'each line holding a literal is flagged, got {lines}'

    def test_find_double_backticks_with_escape_before_literal_returns_its_written_line(self) -> None:
        #: Given
        source = dedent('''\
            def f() -> None:
                """Summary.\\n\\nFirst line.

                Reads ``path``.
                """
            ''')

        #: When
        lines = find_double_backticks(source)

        #: Then
        assert lines == [4], f'a `\\n` escape does not shift the line, got {lines}'

    def test_find_double_backticks_with_backslash_continuation_before_literal_returns_its_written_line(self) -> None:
        #: Given
        source = dedent('''\
            def f() -> None:
                """Summary, \\
                continued.

                Reads ``path``.
                """
            ''')

        #: When
        lines = find_double_backticks(source)

        #: Then
        assert lines == [5], f'a backslash before a line break does not shift the line, got {lines}'

    def test_find_double_backticks_with_literal_inside_fence_returns_only_the_one_outside(self) -> None:
        #: Given
        source = dedent('''\
            def f() -> None:
                """Summary.

                ```rst
                Literal ``text``.
                ```

                Outside ``fence``.
                """
            ''')

        #: When
        lines = find_double_backticks(source)

        #: Then
        assert lines == [8], f'a fenced block is skipped and the text after it is read, got {lines}'

    def test_find_double_backticks_with_single_backticks_and_fence_returns_nothing(self) -> None:
        #: Given
        source = dedent('''\
            """Reads `path`, then:

            ```python
            x = 1
            ```
            """
            ''')

        #: When
        lines = find_double_backticks(source)

        #: Then
        assert lines == [], f'single backticks and a fence are accepted, got {lines}'

    def test_find_double_backticks_with_literal_outside_docstrings_returns_nothing(self) -> None:
        #: Given
        source = dedent("""\
            # A comment about ``path``.
            TEXT = "Not a docstring: ``path``."


            def f() -> None:
                value = "Also ``not``."
            """)

        #: When
        lines = find_double_backticks(source)

        #: Then
        assert lines == [], f'a comment or a string that documents nothing is left alone, got {lines}'


@pytest.mark.it
class TestMain:
    def test_main_with_a_literal_prints_path_line_and_hint_and_returns_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        module = tmp_path / 'bad.py'
        module.write_text('"""Reads ``path``."""\n', encoding='utf-8')

        #: When
        status = main([str(tmp_path)])

        #: Then
        output = capsys.readouterr().out
        assert status == 1, f'a literal fails the check, got {status} with output {output!r}'
        assert output == f'{module}:1: double-backtick literal in a docstring; use single backticks\n', (
            'the hit is reported as path:line with the fix hint'
        )

    def test_main_with_a_clean_tree_prints_nothing_and_returns_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        #: Given
        (tmp_path / 'good.py').write_text('"""Reads `path`."""\n', encoding='utf-8')

        #: When
        status = main([str(tmp_path)])

        #: Then
        output = capsys.readouterr().out
        assert status == 0, f'a clean tree passes, got {status} with output {output!r}'
        assert output == '', f'nothing is reported for a clean tree, got {output!r}'
