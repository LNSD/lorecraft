"""Counting the prose words of a text, as a section's word cap and a title's word cap count them."""

import pytest

from ..words import count_words


@pytest.mark.unit
class TestCountWords:
    def test_count_words_with_empty_text_returns_zero(self) -> None:
        #: Given
        text = ''

        #: When
        words = count_words(text)

        #: Then
        assert words == 0, f'empty text holds no word, got {words}'

    def test_count_words_with_whitespace_alone_returns_zero(self) -> None:
        #: Given
        text = ' \t \n '

        #: When
        words = count_words(text)

        #: Then
        assert words == 0, f'whitespace separates words and is none itself, got {words}'

    def test_count_words_with_runs_of_whitespace_counts_each_token_once(self) -> None:
        #: Given
        text = 'Run  it\tonce,\nthen again.'

        #: When
        words = count_words(text)

        #: Then
        assert words == 5, f'any run of whitespace separates two words, and punctuation is part of one, got {words}'
