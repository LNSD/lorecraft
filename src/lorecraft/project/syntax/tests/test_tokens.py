"""Counting a text's ``o200k_base`` tokens from the vocabulary shipped in the package, never downloaded.

The expected counts are what OpenAI's own ``tiktoken.get_encoding('o200k_base')`` returns for the same text; they
are literals here because that call downloads the vocabulary, and no test reaches the network.
"""

import hashlib
from importlib.resources import files
from typing import Final

import pytest

from ..tokens import count_tokens

O200K_BASE_SHA256: Final[str] = '446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d'
"""The hash tiktoken checks OpenAI's published ``o200k_base.tiktoken`` against, in `tiktoken_ext/openai_public.py`."""


@pytest.mark.unit
class TestCountTokens:
    def test_count_tokens_with_empty_text_returns_zero(self) -> None:
        #: Given
        text = ''

        #: When
        tokens = count_tokens(text)

        #: Then
        assert tokens == 0, f'empty text holds no tokens, got {tokens}'

    def test_count_tokens_with_two_common_words_returns_two(self) -> None:
        #: Given
        text = 'hello world'

        #: When
        tokens = count_tokens(text)

        #: Then
        assert tokens == 2, f'o200k_base encodes `hello` and ` world` as one token each, got {tokens}'

    def test_count_tokens_with_a_markdown_title_counts_its_markers(self) -> None:
        #: Given
        text = '# Guide\n\none two three\n'

        #: When
        tokens = count_tokens(text)

        #: Then
        assert tokens == 7, f'o200k_base encodes this text in 7 tokens, got {tokens}'

    def test_count_tokens_with_special_token_text_counts_it_as_ordinary_text(self) -> None:
        #: Given
        text = '<|endoftext|>'

        #: When
        tokens = count_tokens(text)

        #: Then
        assert tokens == 7, f'a special token written in a document is plain text, not one control token, got {tokens}'


@pytest.mark.unit
class TestShippedVocabulary:
    def test_shipped_vocabulary_hash_matches_openai_published_o200k_base(self) -> None:
        #: Given
        vocabulary = files('lorecraft.project.syntax').joinpath('o200k_base.tiktoken').read_bytes()

        #: When
        digest = hashlib.sha256(vocabulary).hexdigest()

        #: Then
        assert digest == O200K_BASE_SHA256, 'the shipped vocabulary is byte for byte the one OpenAI publishes'
