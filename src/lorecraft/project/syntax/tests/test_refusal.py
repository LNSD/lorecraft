"""Wording the constructs the YAML subset leaves out, as `FM002` reports them."""

from lorecraft.yaml.problem import (
    Alias,
    Anchor,
    CollectionInFlow,
    CollectionKey,
    Directive,
    DocumentMarker,
    EmptyKey,
    EscapeBeyondUnicode,
    ExplicitKey,
    FlowCollectionRoot,
    IndentationIndicator,
    LineSeparator,
    MergeKey,
    NestedBlockSequence,
    NonStringKey,
    SpreadFlowCollection,
    Tag,
)

from ..refusal import describe_refusal, refusal_help


class TestDescribeRefusal:
    def test_describe_refusal_with_a_directive_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = Directive('%YAML')

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'found the directive %YAML, which frontmatter does not allow', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_a_document_marker_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = DocumentMarker('---')

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'found the document marker ---, which frontmatter does not allow', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_an_alias_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = Alias('x')

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'found the alias *x, which frontmatter does not allow', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_an_anchor_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = Anchor('x')

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'found the anchor &x, which frontmatter does not allow', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_a_tag_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = Tag('!!str')

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == "found the tag '!!str', which frontmatter does not allow", (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_a_merge_key_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = MergeKey()

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'found the merge key <<, which frontmatter does not allow', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_a_collection_key_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = CollectionKey()

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'found a collection as a key, which frontmatter does not allow', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_a_non_string_key_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = NonStringKey('1')

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'found the non-string key 1, which frontmatter does not allow', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_a_flow_collection_root_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = FlowCollectionRoot()

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'found a flow collection as the block, which frontmatter does not allow', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_a_collection_in_a_flow_collection_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = CollectionInFlow()

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'found a collection inside a flow collection, which frontmatter does not allow', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_a_nested_block_sequence_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = NestedBlockSequence()

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'found a block sequence as an item of a block sequence, which frontmatter does not allow', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_an_escape_beyond_unicode_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = EscapeBeyondUnicode()

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'found an escape that names no Unicode character, which frontmatter does not allow', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_an_explicit_key_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = ExplicitKey()

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'found an explicit key, which frontmatter does not allow', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_an_empty_key_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = EmptyKey()

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'found an empty key, which frontmatter does not allow', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_an_indentation_indicator_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = IndentationIndicator()

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'found a block scalar indentation indicator, which frontmatter does not allow', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_a_spread_flow_collection_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = SpreadFlowCollection()

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'found a flow collection spread over lines, which frontmatter does not allow', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )

    def test_describe_refusal_with_a_line_separator_words_it_as_fm002_does(self) -> None:
        #: Given
        construct = LineSeparator('\u2028')

        #: When
        problem = describe_refusal(construct)

        #: Then
        assert problem == 'the block holds U+2028, which is not a line break here', (
            f'{construct!r} is worded as FM002 words it, got {problem!r}'
        )


class TestRefusalHelp:
    def test_refusal_help_with_a_line_separator_returns_the_line_feed_advice(self) -> None:
        #: Given
        construct = LineSeparator('\x85')

        #: When
        help_text = refusal_help(construct)

        #: Then
        assert help_text == 'Use a line feed, or remove it', f'a separator has a help, got {help_text!r}'

    def test_refusal_help_with_an_alias_returns_none(self) -> None:
        #: Given
        construct = Alias('x')

        #: When
        help_text = refusal_help(construct)

        #: Then
        assert help_text is None, f'any other construct has no help, got {help_text!r}'
