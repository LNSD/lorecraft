"""The fields of a skill's frontmatter that parse, each on its own, keyed by the field.

The `allowed-tools` entries are tested through `parse_allowed_tools`, since each shape of a malformed entry is one
judgement of it.
"""

import pytest

from lorecraft.project.syntax import parse_frontmatter

from ..skill_fields import (
    AllowedTool,
    AllowedTools,
    CommaSeparated,
    NotATool,
    SkillField,
    UnbalancedParentheses,
    parse_allowed_tools,
    parse_skill_fields,
)
from ..skill_frontmatter import SkillName


def _fields(*lines: str) -> dict[SkillField, object]:
    """The fields parsed from a frontmatter block holding the lines."""
    text = '---\n' + '\n'.join(lines) + '\n---\n# Body\n'
    return dict(parse_skill_fields(parse_frontmatter(text)))


class TestParseSkillFields:
    def test_parse_with_a_conforming_name_keys_the_value_object_by_the_field(self) -> None:
        #: When
        fields = _fields('name: review')

        #: Then
        assert fields == {SkillField.NAME: SkillName('review')}, 'a written, conforming field is parsed'

    def test_parse_with_a_rejected_name_still_parses_the_other_fields(self) -> None:
        #: When
        fields = _fields('name: Not A Name', 'allowed-tools: Read')

        #: Then
        assert fields == {SkillField.ALLOWED_TOOLS: parse_allowed_tools('Read')}, (
            'a field the specification rejects has no entry, and does not hold back its neighbours'
        )

    @pytest.mark.parametrize('line', ['allowed-tools:', 'allowed-tools: 12', 'allowed-tools: [Read]'])
    def test_parse_with_a_null_or_non_string_allowed_tools_holds_no_entry(self, line: str) -> None:
        #: When
        fields = _fields(line)

        #: Then
        assert fields == {}, 'only a string is an `allowed-tools` value'

    def test_parse_without_a_mapping_block_holds_no_field(self) -> None:
        #: When
        fields = parse_skill_fields(parse_frontmatter('# Review\n'))

        #: Then
        assert fields == {}, 'a missing block holds no field'


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
