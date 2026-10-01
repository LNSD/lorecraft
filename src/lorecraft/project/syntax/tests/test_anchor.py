"""A heading's anchor.

The github-slugger rule that derives one from a heading's text, the numbering of a repeat, the normalisation a
link's fragment goes through before it is compared with one, and the format every anchor holds.
"""

import pytest

from ..anchor import Anchor, InvalidAnchorError


@pytest.mark.unit
class TestAnchor:
    def test_anchor_with_an_uppercase_letter_raises_invalid_anchor(self) -> None:
        #: Given
        rejected = 'Usage'

        #: When
        with pytest.raises(InvalidAnchorError) as exc_info:
            Anchor(rejected)

        #: Then
        assert (exc_info.value.value, exc_info.value.position, exc_info.value.character) == (rejected, 0, 'U'), (
            'the error carries the rejected value and its first character outside the format'
        )

    def test_anchor_with_a_space_raises_invalid_anchor(self) -> None:
        #: Given
        rejected = 'getting started'

        #: When
        with pytest.raises(InvalidAnchorError) as exc_info:
            Anchor(rejected)

        #: Then
        assert (exc_info.value.position, exc_info.value.character) == (7, ' '), (
            'a space is no anchor character, since a heading turns each of its spaces into a hyphen'
        )

    def test_anchor_with_punctuation_raises_invalid_anchor(self) -> None:
        #: Given
        rejected = 'faq!'

        #: When
        with pytest.raises(InvalidAnchorError) as exc_info:
            Anchor(rejected)

        #: Then
        assert (exc_info.value.position, exc_info.value.character) == (3, '!'), (
            'punctuation other than a hyphen-minus or a connector is no anchor character'
        )

    def test_anchor_with_an_empty_value_holds_it(self) -> None:
        #: Given
        value = ''

        #: When
        anchor = Anchor(value)

        #: Then
        assert anchor.value == '', 'the empty anchor is valid, since a heading of only punctuation has it'

    def test_anchor_of_a_valid_value_prints_as_its_value(self) -> None:
        #: Given
        anchor = Anchor('getting-started')

        #: When
        text = str(anchor)

        #: Then
        assert text == 'getting-started', f'an anchor prints as its bare value, without a #, got {text!r}'


@pytest.mark.unit
class TestAnchorFromHeading:
    def test_anchor_from_heading_lowercases_the_text_and_hyphenates_each_space(self) -> None:
        #: Given
        text = 'Getting Started'

        #: When
        anchor = Anchor.from_heading(text)

        #: Then
        assert anchor == Anchor('getting-started'), (
            'the anchor is the heading text lowercased, each space turned into a hyphen'
        )

    def test_anchor_from_heading_with_punctuation_drops_it_without_collapsing_the_spaces(self) -> None:
        #: Given
        text = 'C++ & Rust: a (short) guide_v2 - again!'

        #: When
        anchor = Anchor.from_heading(text)

        #: Then
        assert anchor == Anchor('c--rust-a-short-guide_v2---again'), (
            'punctuation and symbols are dropped, the underscore and hyphen kept, and each space stays a hyphen'
        )

    def test_anchor_from_heading_with_letters_outside_ascii_keeps_them(self) -> None:
        #: Given
        text = 'Ünïcödé Straße'

        #: When
        anchor = Anchor.from_heading(text)

        #: Then
        assert anchor == Anchor('ünïcödé-straße'), 'a letter in any script is kept, and lowercased'

    def test_anchor_from_heading_with_combining_marks_keeps_them(self) -> None:
        #: Given
        text = 'हिन्दी'

        #: When
        anchor = Anchor.from_heading(text)

        #: Then
        assert anchor == Anchor('हिन्दी'), (
            'a combining mark is part of the letter it follows, so the Devanagari vowel signs and virama stay'
        )

    def test_anchor_from_heading_with_a_decomposed_accent_keeps_it(self) -> None:
        #: Given
        text = 'Café'

        #: When
        anchor = Anchor.from_heading(text)

        #: Then
        assert anchor == Anchor('café'), (
            'a decomposed acute accent is a combining mark, kept after its letter rather than normalized'
        )

    def test_anchor_from_heading_with_a_dotted_capital_i_keeps_its_lowercase_dot(self) -> None:
        #: Given
        text = 'İstanbul'

        #: When
        anchor = Anchor.from_heading(text)

        #: Then
        assert anchor == Anchor('i̇stanbul'), (
            'a dotted capital I lowercases to an i and a combining dot above, and both are anchor characters'
        )

    def test_anchor_from_heading_with_a_final_capital_sigma_lowercases_it_to_the_final_form(self) -> None:
        #: Given
        text = 'ΟΔΟΣ'

        #: When
        anchor = Anchor.from_heading(text)

        #: Then
        assert anchor == Anchor('οδος'), 'a capital sigma ending a word lowercases to the final sigma'

    def test_anchor_from_heading_with_other_numbers_drops_them(self) -> None:
        #: Given
        text = '½ ② x'

        #: When
        anchor = Anchor.from_heading(text)

        #: Then
        assert anchor == Anchor('--x'), 'a vulgar fraction and a circled digit are other numbers, which are dropped'

    def test_anchor_from_heading_with_connector_punctuation_keeps_it(self) -> None:
        #: Given
        text = 'a‿b'

        #: When
        anchor = Anchor.from_heading(text)

        #: Then
        assert anchor == Anchor('a‿b'), 'an undertie is connector punctuation, kept as the underscore is'

    def test_anchor_from_heading_with_an_en_dash_drops_it(self) -> None:
        #: Given
        text = 'a – b'

        #: When
        anchor = Anchor.from_heading(text)

        #: Then
        assert anchor == Anchor('a--b'), (
            'only the hyphen-minus survives among the dashes, so an en dash is dropped and its spaces remain'
        )

    def test_anchor_from_heading_with_only_punctuation_returns_the_empty_anchor(self) -> None:
        #: Given
        text = '?!'

        #: When
        anchor = Anchor.from_heading(text)

        #: Then
        assert anchor == Anchor(''), 'a heading with no anchor character gives the empty anchor'

    def test_anchor_from_heading_with_empty_text_returns_the_empty_anchor(self) -> None:
        #: Given
        text = ''

        #: When
        anchor = Anchor.from_heading(text)

        #: Then
        assert anchor == Anchor(''), 'an empty heading gives the empty anchor'


@pytest.mark.unit
class TestAnchorNumbered:
    def test_anchor_numbered_with_a_repeat_count_appends_a_hyphen_and_the_number(self) -> None:
        #: Given
        anchor = Anchor('usage')

        #: When
        numbered = anchor.numbered(2)

        #: Then
        assert numbered == Anchor('usage-2'), 'a repeated heading takes its bare anchor, a hyphen and its number'

    def test_anchor_numbered_of_the_empty_anchor_is_the_hyphenated_number(self) -> None:
        #: Given
        anchor = Anchor('')

        #: When
        numbered = anchor.numbered(1)

        #: Then
        assert numbered == Anchor('-1'), 'a repeat of a heading with the empty anchor is numbered as any other'


@pytest.mark.unit
class TestAnchorFromFragment:
    def test_anchor_from_fragment_with_an_uppercase_letter_lowercases_it(self) -> None:
        #: Given
        fragment = 'Usage'

        #: When
        anchor = Anchor.from_fragment(fragment)

        #: Then
        assert anchor == Anchor('usage'), 'GitHub resolves a fragment regardless of case'

    def test_anchor_from_fragment_with_percent_encoding_decodes_it(self) -> None:
        #: Given
        fragment = 'Stra%C3%9Fe'

        #: When
        anchor = Anchor.from_fragment(fragment)

        #: Then
        assert anchor == Anchor('straße'), 'the parser percent-encodes a destination, so the fragment is decoded'

    def test_anchor_from_fragment_with_a_dotted_capital_i_lowercases_it_as_a_heading_does(self) -> None:
        #: Given
        fragment = '%C4%B0stanbul'

        #: When
        anchor = Anchor.from_fragment(fragment)

        #: Then
        assert anchor == Anchor('i̇stanbul'), (
            'a fragment is lowercased as a heading is, so it reaches the anchor the heading İstanbul gives'
        )

    def test_anchor_from_fragment_with_an_encoded_space_returns_none(self) -> None:
        #: Given
        fragment = 'getting%20started'

        #: When
        anchor = Anchor.from_fragment(fragment)

        #: Then
        assert anchor is None, 'a fragment holding a space is no anchor, so no heading can have it'

    def test_anchor_from_fragment_with_punctuation_returns_none(self) -> None:
        #: Given
        fragment = 'faq!'

        #: When
        anchor = Anchor.from_fragment(fragment)

        #: Then
        assert anchor is None, 'a fragment holding punctuation an anchor drops names no heading'

    def test_anchor_from_fragment_with_an_empty_fragment_returns_the_empty_anchor(self) -> None:
        #: Given
        fragment = ''

        #: When
        anchor = Anchor.from_fragment(fragment)

        #: Then
        assert anchor == Anchor(''), 'the empty fragment is the empty anchor, which a heading can have'
