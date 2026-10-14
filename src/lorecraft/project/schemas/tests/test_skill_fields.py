"""The entries an `allowed-tools` value lists, each judged on its own.

Each shape of a malformed entry is one judgement of it.
"""

from ..skill_fields import (
    AllowedTool,
    AllowedTools,
    CommaSeparated,
    NotATool,
    UnbalancedParentheses,
    parse_allowed_tools,
)


class TestParseAllowedTools:
    def test_parse_with_whitespace_only_has_no_entries(self) -> None:
        #: When
        parsed = parse_allowed_tools('   ')

        #: Then
        assert parsed == AllowedTools('   ', ()), 'the text is kept whole and no entry is listed'

    def test_parse_keeps_a_pattern_with_spaces_and_commas_as_one_entry(self) -> None:
        #: When
        parsed = parse_allowed_tools('Read Bash(git add *, git rm *)')

        #: Then
        assert parsed.entries == (AllowedTool('Read'), AllowedTool('Bash(git add *, git rm *)')), (
            'whitespace and commas inside parentheses belong to the pattern'
        )

    def test_parse_with_commas_between_tools_suggests_spaces(self) -> None:
        #: When
        parsed = parse_allowed_tools('Read,Grep')

        #: Then
        assert parsed.entries == (CommaSeparated('Read,Grep', 'Read Grep'),), 'a comma separates tools in one entry'

    def test_parse_with_an_unclosed_pattern_is_unbalanced(self) -> None:
        #: When
        parsed = parse_allowed_tools('Bash(git add *')

        #: Then
        assert parsed.entries == (UnbalancedParentheses('Bash(git add *'),), 'the pattern is never closed'

    def test_parse_with_a_symbol_is_not_a_tool(self) -> None:
        #: When
        parsed = parse_allowed_tools('@read')

        #: Then
        assert parsed.entries == (NotATool('@read'),), 'a tool name holds letters, digits, underscores and hyphens'
