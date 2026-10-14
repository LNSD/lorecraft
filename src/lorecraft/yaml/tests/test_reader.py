"""Reading a YAML text: the tree it builds, where each node sits, and what stops a read."""

from textwrap import dedent

import pytest
from ruamel.yaml.error import MarkedYAMLError
from ruamel.yaml.reader import ReaderError

from lorecraft.core.num import NonZeroUnsignedInt

from ..basic_yaml import RefusedAliasError, RefusedFlowBlockError
from ..reader import YamlEventStream, read_document
from ..tree import YamlMapping, YamlPosition, YamlScalar, YamlSequence, YamlValue


def _at(line: int, column: int) -> YamlPosition:
    return YamlPosition(NonZeroUnsignedInt(line), NonZeroUnsignedInt(column))


def _read(text: str) -> YamlValue | None:
    return read_document(YamlEventStream(text))


@pytest.mark.unit
class TestReadYaml:
    def test_read_yaml_with_an_empty_text_returns_none(self) -> None:
        #: Given
        text = ''

        #: When
        root = _read(text)

        #: Then
        assert root is None, f'{text!r} holds no document, got {root!r}'

    def test_read_yaml_with_a_blank_line_returns_none(self) -> None:
        #: Given
        text = '\n'

        #: When
        root = _read(text)

        #: Then
        assert root is None, f'{text!r} holds no document, got {root!r}'

    def test_read_yaml_with_only_a_comment_returns_none(self) -> None:
        #: Given
        text = '# only a comment\n'

        #: When
        root = _read(text)

        #: Then
        assert root is None, f'{text!r} holds no document, got {root!r}'

    def test_read_yaml_with_a_mapping_returns_each_key_and_value_at_its_position(self) -> None:
        #: Given
        text = dedent("""\
            name: guide

            type: rule
            """)

        #: When
        root = _read(text)

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
        root = _read(text)

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
        root = _read(text)

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
        root = _read(text)

        #: Then
        assert root == YamlScalar('guide', _at(1, 1)), f'a text of one scalar is its own root, got {root!r}'

    def test_read_yaml_with_a_tilde_returns_a_scalar_of_the_type_its_text_reads_as(self) -> None:
        #: Given
        text = '~'

        #: When
        root = _read(text)

        #: Then
        assert isinstance(root, YamlScalar), f'{text!r} is a scalar, got {root!r}'
        assert root.value is None, f'{text!r} reads as None, got {root.value!r}'

    def test_read_yaml_with_the_word_true_returns_a_scalar_of_the_type_its_text_reads_as(self) -> None:
        #: Given
        text = 'true'

        #: When
        root = _read(text)

        #: Then
        assert isinstance(root, YamlScalar), f'{text!r} is a scalar, got {root!r}'
        assert root.value is True, f'{text!r} reads as True, got {root.value!r}'

    def test_read_yaml_with_an_integer_returns_a_scalar_of_the_type_its_text_reads_as(self) -> None:
        #: Given
        text = '1'

        #: When
        root = _read(text)

        #: Then
        assert isinstance(root, YamlScalar), f'{text!r} is a scalar, got {root!r}'
        assert root.value == 1, f'{text!r} reads as 1, got {root.value!r}'
        assert type(root.value) is int, f'{text!r} is a int, got {type(root.value).__name__}'

    def test_read_yaml_with_a_decimal_fraction_returns_a_scalar_of_the_type_its_text_reads_as(self) -> None:
        #: Given
        text = '1.0'

        #: When
        root = _read(text)

        #: Then
        assert isinstance(root, YamlScalar), f'{text!r} is a scalar, got {root!r}'
        assert root.value == 1.0, f'{text!r} reads as 1.0, got {root.value!r}'
        assert type(root.value) is float, f'{text!r} is a float, got {type(root.value).__name__}'

    def test_read_yaml_with_a_single_quoted_integer_returns_a_scalar_of_the_type_its_text_reads_as(self) -> None:
        #: Given
        text = "'1'"

        #: When
        root = _read(text)

        #: Then
        assert isinstance(root, YamlScalar), f'{text!r} is a scalar, got {root!r}'
        assert root.value == '1', f'{text!r} reads as 1, got {root.value!r}'
        assert type(root.value) is str, f'{text!r} is a str, got {type(root.value).__name__}'

    def test_read_yaml_with_a_double_quoted_boolean_returns_a_scalar_of_the_type_its_text_reads_as(self) -> None:
        #: Given
        text = '"true"'

        #: When
        root = _read(text)

        #: Then
        assert isinstance(root, YamlScalar), f'{text!r} is a scalar, got {root!r}'
        assert root.value == 'true', f'{text!r} reads as true, got {root.value!r}'
        assert type(root.value) is str, f'{text!r} is a str, got {type(root.value).__name__}'

    def test_read_yaml_with_the_word_yes_returns_a_scalar_of_the_type_its_text_reads_as(self) -> None:
        #: Given
        text = 'yes'

        #: When
        root = _read(text)

        #: Then
        assert isinstance(root, YamlScalar), f'{text!r} is a scalar, got {root!r}'
        assert root.value == 'yes', f'{text!r} reads as yes, got {root.value!r}'
        assert type(root.value) is str, f'{text!r} is a str, got {type(root.value).__name__}'

    def test_read_yaml_with_an_alias_raises_the_refusal(self) -> None:
        #: Given
        text = 'a: *x\n'

        #: When
        with pytest.raises(RefusedAliasError) as raised:
            _read(text)

        #: Then
        assert raised.value.anchor == 'x', f'the alias names the anchor it points at, got {raised.value.anchor!r}'

    def test_read_yaml_with_a_flow_collection_as_the_whole_text_raises_the_refusal(self) -> None:
        #: Given
        text = '[a, b]\n'

        #: When
        with pytest.raises(RefusedFlowBlockError) as raised:
            _read(text)

        #: Then
        assert raised.value.mark.line == 0, f'a flow collection is not a block, got {raised.value.mark}'

    def test_read_yaml_with_a_control_character_raises_the_reader_error(self) -> None:
        #: Given
        text = 'a: \x07\n'

        #: When
        with pytest.raises(ReaderError) as raised:
            _read(text)

        #: Then
        assert raised.value.character == 0x07, f'a control character fails the reader, got {raised.value}'

    def test_read_yaml_with_a_syntax_error_raises_the_marked_error(self) -> None:
        #: Given
        text = 'a: [1, 2\n'

        #: When
        with pytest.raises(MarkedYAMLError) as raised:
            _read(text)

        #: Then
        assert raised.value.problem_mark is not None, f'a bracket left open is a syntax error, got {raised.value}'

    def test_read_yaml_with_an_explicit_key_reads_to_the_end_and_records_the_refusal(self) -> None:
        #: Given
        text = '? a\n: 1\n'
        stream = YamlEventStream(text)
        read_document(stream)

        #: When
        refusal = stream.first_refusal()

        #: Then
        assert refusal is not None, 'the scanner recorded the explicit key'
        assert refusal.construct == 'an explicit key', f'an explicit key is recorded as one, got {refusal}'
