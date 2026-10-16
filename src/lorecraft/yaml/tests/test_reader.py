"""Reading a YAML text: the tree it builds, where each node sits, and the problem that stops a read."""

from textwrap import dedent

import pytest

from lorecraft.core.num import NonZeroUnsignedInt

from ..problem import (
    Alias,
    ControlCharacterProblem,
    ExplicitKey,
    FlowCollectionRoot,
    NestingTooDeepProblem,
    RefusedConstructProblem,
    SyntaxErrorProblem,
)
from ..reader import read_yaml
from ..tree import YamlMapping, YamlPosition, YamlScalar, YamlSequence


def _at(line: int, column: int) -> YamlPosition:
    return YamlPosition(NonZeroUnsignedInt(line), NonZeroUnsignedInt(column))


@pytest.mark.unit
class TestReadYaml:
    def test_read_yaml_with_an_empty_text_returns_none(self) -> None:
        #: Given
        text = ''

        #: When
        root = read_yaml(text)

        #: Then
        assert root is None, f'{text!r} holds no document, got {root!r}'

    def test_read_yaml_with_a_blank_line_returns_none(self) -> None:
        #: Given
        text = '\n'

        #: When
        root = read_yaml(text)

        #: Then
        assert root is None, f'{text!r} holds no document, got {root!r}'

    def test_read_yaml_with_only_a_comment_returns_none(self) -> None:
        #: Given
        text = '# only a comment\n'

        #: When
        root = read_yaml(text)

        #: Then
        assert root is None, f'{text!r} holds no document, got {root!r}'

    def test_read_yaml_with_a_mapping_returns_each_key_and_value_at_its_position(self) -> None:
        #: Given
        text = dedent("""\
            name: guide

            type: rule
            """)

        #: When
        root = read_yaml(text)

        #: Then
        assert isinstance(root, YamlMapping), f'a block mapping is a mapping, got {root!r}'
        assert [(key.name, key.position) for key, _value in root.entries] == [
            ('name', _at(1, 1)),
            ('type', _at(3, 1)),
        ], 'each key is at the line and column it is written, counted from 1'
        assert [value.position for _key, value in root.entries] == [_at(1, 7), _at(3, 7)], (
            'each value is at the line and column its text starts'
        )

    def test_read_yaml_with_a_repeated_key_keeps_every_occurrence_in_written_order(self) -> None:
        #: Given
        text = 'name: first\nname: last\n'

        #: When
        root = read_yaml(text)

        #: Then
        assert isinstance(root, YamlMapping), f'a block mapping is a mapping, got {root!r}'
        assert [value for _key, value in root.entries] == [
            YamlScalar('first', _at(1, 7)),
            YamlScalar('last', _at(2, 7)),
        ], 'a key written twice appears once per occurrence, which the reader of the tree resolves'

    def test_read_yaml_with_a_sequence_of_mappings_returns_the_items_in_order(self) -> None:
        #: Given
        text = dedent("""\
            items:
              - a: 1
              - a: 2
            """)

        #: When
        root = read_yaml(text)

        #: Then
        assert isinstance(root, YamlMapping), f'a block mapping is a mapping, got {root!r}'
        sequence = root.entries[0][1]
        assert isinstance(sequence, YamlSequence), f'a block sequence is a sequence, got {sequence!r}'
        assert [item.position for item in sequence.items] == [_at(2, 5), _at(3, 5)], (
            'each item is the mapping that starts at its first key'
        )

    def test_read_yaml_with_a_scalar_root_returns_the_scalar(self) -> None:
        #: Given
        text = 'guide\n'

        #: When
        root = read_yaml(text)

        #: Then
        assert root == YamlScalar('guide', _at(1, 1)), f'a text of one scalar is its own root, got {root!r}'

    def test_read_yaml_with_a_tilde_returns_a_scalar_of_the_type_its_text_reads_as(self) -> None:
        #: Given
        text = '~'

        #: When
        root = read_yaml(text)

        #: Then
        assert isinstance(root, YamlScalar), f'{text!r} is a scalar, got {root!r}'
        assert root.value is None, f'{text!r} reads as None, got {root.value!r}'

    def test_read_yaml_with_the_word_true_returns_a_scalar_of_the_type_its_text_reads_as(self) -> None:
        #: Given
        text = 'true'

        #: When
        root = read_yaml(text)

        #: Then
        assert isinstance(root, YamlScalar), f'{text!r} is a scalar, got {root!r}'
        assert root.value is True, f'{text!r} reads as True, got {root.value!r}'

    def test_read_yaml_with_an_integer_returns_a_scalar_of_the_type_its_text_reads_as(self) -> None:
        #: Given
        text = '1'

        #: When
        root = read_yaml(text)

        #: Then
        assert isinstance(root, YamlScalar), f'{text!r} is a scalar, got {root!r}'
        assert root.value == 1, f'{text!r} reads as 1, got {root.value!r}'
        assert type(root.value) is int, f'{text!r} is a int, got {type(root.value).__name__}'

    def test_read_yaml_with_a_decimal_fraction_returns_a_scalar_of_the_type_its_text_reads_as(self) -> None:
        #: Given
        text = '1.0'

        #: When
        root = read_yaml(text)

        #: Then
        assert isinstance(root, YamlScalar), f'{text!r} is a scalar, got {root!r}'
        assert root.value == 1.0, f'{text!r} reads as 1.0, got {root.value!r}'
        assert type(root.value) is float, f'{text!r} is a float, got {type(root.value).__name__}'

    def test_read_yaml_with_a_single_quoted_integer_returns_a_scalar_of_the_type_its_text_reads_as(self) -> None:
        #: Given
        text = "'1'"

        #: When
        root = read_yaml(text)

        #: Then
        assert isinstance(root, YamlScalar), f'{text!r} is a scalar, got {root!r}'
        assert root.value == '1', f'{text!r} reads as 1, got {root.value!r}'
        assert type(root.value) is str, f'{text!r} is a str, got {type(root.value).__name__}'

    def test_read_yaml_with_a_double_quoted_boolean_returns_a_scalar_of_the_type_its_text_reads_as(self) -> None:
        #: Given
        text = '"true"'

        #: When
        root = read_yaml(text)

        #: Then
        assert isinstance(root, YamlScalar), f'{text!r} is a scalar, got {root!r}'
        assert root.value == 'true', f'{text!r} reads as true, got {root.value!r}'
        assert type(root.value) is str, f'{text!r} is a str, got {type(root.value).__name__}'

    def test_read_yaml_with_the_word_yes_returns_a_scalar_of_the_type_its_text_reads_as(self) -> None:
        #: Given
        text = 'yes'

        #: When
        root = read_yaml(text)

        #: Then
        assert isinstance(root, YamlScalar), f'{text!r} is a scalar, got {root!r}'
        assert root.value == 'yes', f'{text!r} reads as yes, got {root.value!r}'
        assert type(root.value) is str, f'{text!r} is a str, got {type(root.value).__name__}'

    def test_read_yaml_with_an_alias_returns_the_refused_construct_at_the_alias(self) -> None:
        #: Given
        text = 'a: *x\n'

        #: When
        problem = read_yaml(text)

        #: Then
        assert problem == RefusedConstructProblem(Alias('x'), _at(1, 4)), (
            f'an alias is refused where it is written, got {problem!r}'
        )

    def test_read_yaml_with_a_flow_collection_as_the_whole_text_returns_the_refused_construct(self) -> None:
        #: Given
        text = '[a, b]\n'

        #: When
        problem = read_yaml(text)

        #: Then
        assert problem == RefusedConstructProblem(FlowCollectionRoot(), _at(1, 1)), (
            f'a flow collection is not a block, got {problem!r}'
        )

    def test_read_yaml_with_a_control_character_returns_its_code_and_index(self) -> None:
        #: Given
        text = 'a: \x07\n'

        #: When
        problem = read_yaml(text)

        #: Then
        assert problem == ControlCharacterProblem(code=7, position=_at(1, 4)), (
            f'a control character is refused, got {problem!r}'
        )

    def test_read_yaml_with_byte_order_marks_counts_them_in_the_columns(self) -> None:
        #: Given
        text = 'a: "\ufeff\ufeff\\q"\n'

        #: When
        problem = read_yaml(text)

        #: Then
        assert isinstance(problem, SyntaxErrorProblem), f'an unknown escape is a syntax error, got {problem!r}'
        assert problem.position == _at(1, 8), f'the marks take a column each, got {problem.position!r}'

    def test_read_yaml_with_a_control_character_after_byte_order_marks_returns_its_character_column(self) -> None:
        #: Given
        text = '\ufeff\ufeffa: \x07\n'

        #: When
        problem = read_yaml(text)

        #: Then
        assert problem == ControlCharacterProblem(code=7, position=_at(1, 6)), f'got {problem!r}'

    def test_read_yaml_with_a_syntax_error_returns_the_parser_facts_and_the_position(self) -> None:
        #: Given
        text = 'a: b: c\n'

        #: When
        problem = read_yaml(text)

        #: Then
        assert isinstance(problem, SyntaxErrorProblem), f'a second colon is a syntax error, got {problem!r}'
        assert problem.position is not None, 'the parser marks where it found the problem'
        assert problem.problem != '', 'the parser words what it found'

    def test_read_yaml_with_an_explicit_key_returns_the_recorded_construct_at_the_key(self) -> None:
        #: Given
        text = '? a\n: 1\n'

        #: When
        problem = read_yaml(text)

        #: Then
        assert problem == RefusedConstructProblem(ExplicitKey(), _at(1, 1)), (
            f'an explicit key is recorded where it is written, got {problem!r}'
        )

    def test_read_yaml_with_a_construct_below_an_error_returns_the_construct_written_first(self) -> None:
        #: Given
        text = '? a\n: b: c\n'

        #: When
        problem = read_yaml(text)

        #: Then
        assert isinstance(problem, RefusedConstructProblem), f'the explicit key comes first, got {problem!r}'
        assert problem.position == _at(1, 1), 'the construct written above the error is the one reported'

    def test_read_yaml_with_collections_nested_past_the_recursion_limit_returns_the_nesting_problem(self) -> None:
        #: Given
        depth = 10_000
        text = ''.join(f'{" " * (2 * level)}a:\n' for level in range(depth))

        #: When
        problem = read_yaml(text)

        #: Then
        assert problem == NestingTooDeepProblem(), f'a deep text exhausts the stack, got {problem!r}'
