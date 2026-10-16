"""`parse_markdown_frontmatter`'s direct scan against wenmode's frontmatter plugin, which the full parse uses.

The scan finds the frontmatter block without a Markdown pass, so nothing but these tests holds it to the plugin that
`parse_markdown` finds the block with. Each test draws a fixed sample of generated texts, the same on every run, and
lists the texts on which the two find different blocks, or one finds a block and the other none. This tier alone may
import wenmode: the package reads it in `lorecraft.markdown` only.
"""

import random
from dataclasses import dataclass
from typing import Final

import pytest
from wenmode import Wenmode
from wenmode.plugins import frontmatter

from lorecraft.markdown import parse_markdown_frontmatter

BYTE_ORDER_MARK: Final[str] = '\ufeff'
"""The Unicode byte order mark, which a file saved by some editors opens with."""

SAMPLE_SIZE: Final[int] = 500
"""Texts generated for each test."""


class ClosingProbabilityOutOfRangeError(ValueError):
    """A variation's closing probability is outside 0 to 1.

    Attributes:
        closing_probability: The rejected probability.
    """

    closing_probability: float

    def __init__(self, closing_probability: float) -> None:
        self.closing_probability = closing_probability
        super().__init__(f'closing_probability must be from 0 to 1, got {closing_probability}')


@dataclass(frozen=True, slots=True)
class Variation:
    """What a generated text may vary in: each field holds the choices one text draws from.

    A text is an opening delimiter line, some block lines, a closing delimiter line that may be missing, a heading,
    and optionally more `---` lines after it. A test widens the one field it is about and leaves the rest plain.

    Attributes:
        prefixes: What may come before the opening `---` on its line, such as a byte order mark.
        endings: The line ending a text joins all its lines with, one per text.
        delimiter_tails: What may follow `---` on a delimiter line, such as trailing whitespace.
        block_sizes: How many lines the block may hold; 0 is an empty block.
        closing_probability: The chance, from 0 to 1, that a text has its closing delimiter.
        later_delimiters: Whether a text holds more `---` lines after the heading.
    """

    prefixes: tuple[str, ...] = ('',)
    endings: tuple[str, ...] = ('\n',)
    delimiter_tails: tuple[str, ...] = ('',)
    block_sizes: tuple[int, ...] = (1, 2, 3)
    closing_probability: float = 1.0
    later_delimiters: bool = False

    def __post_init__(self) -> None:
        """Reject a closing probability outside 0 to 1.

        Raises:
            ClosingProbabilityOutOfRangeError: If `closing_probability` is not in 0..1.
        """
        if not 0.0 <= self.closing_probability <= 1.0:
            raise ClosingProbabilityOutOfRangeError(self.closing_probability)


def generate_texts(variation: Variation) -> list[str]:
    """Texts drawn from the variation. Every block line is unique, so a block cut in the wrong place shows.

    Args:
        variation: The choices each generated text draws from.
    """
    rng = random.Random(260622)
    texts: list[str] = []
    for _ in range(SAMPLE_SIZE):
        ending = rng.choice(variation.endings)
        lines = [rng.choice(variation.prefixes) + '---' + rng.choice(variation.delimiter_tails)]
        lines.extend(f'key{number}: {number}' for number in range(rng.choice(variation.block_sizes)))
        if rng.random() < variation.closing_probability:
            lines.append('---' + rng.choice(variation.delimiter_tails))
        lines.append('# Guide')
        if variation.later_delimiters:
            lines.extend(['---', 'tail: 1', '---'])
        texts.append(ending.join(lines) + ending)
    return texts


def wenmode_frontmatter(text: str) -> str | None:
    """What wenmode's frontmatter plugin finds in the text, as raw block text.

    Args:
        text: The document's whole text.
    """
    found: list[str] = []

    def record(block: str) -> None:
        found.append(block)

    Wenmode(rules=(), plugins=[frontmatter.configure(load=record)]).parse(text)
    return found[0] if found else None


def disagreements(texts: list[str]) -> list[str]:
    """The texts on which the direct scan and wenmode's plugin do not find the same block.

    Args:
        texts: The documents' whole texts.
    """
    return [text for text in texts if parse_markdown_frontmatter(text) != wenmode_frontmatter(text)]


@pytest.mark.it
class TestVariation:
    def test_init_with_a_negative_closing_probability_raises_closing_probability_out_of_range_error(self) -> None:
        #: Given
        closing_probability = -0.1

        #: When
        with pytest.raises(ClosingProbabilityOutOfRangeError) as exc_info:
            Variation(closing_probability=closing_probability)

        #: Then
        assert 'closing_probability' in str(exc_info.value), 'the error names the field'
        assert '-0.1' in str(exc_info.value), 'the error names the rejected value'

    def test_init_with_a_closing_probability_above_one_raises_closing_probability_out_of_range_error(self) -> None:
        #: Given
        closing_probability = 1.1

        #: When
        with pytest.raises(ClosingProbabilityOutOfRangeError) as exc_info:
            Variation(closing_probability=closing_probability)

        #: Then
        assert 'closing_probability' in str(exc_info.value), 'the error names the field'
        assert '1.1' in str(exc_info.value), 'the error names the rejected value'


@pytest.mark.it
class TestFrontmatterScanAgainstWenmode:
    def test_parse_markdown_frontmatter_with_varied_line_endings_finds_the_block_wenmode_finds(self) -> None:
        #: Given
        texts = generate_texts(Variation(endings=('\n', '\r\n', '\r'), closing_probability=0.8))

        #: When
        differing = disagreements(texts)

        #: Then
        assert differing == [], 'LF and CRLF end a delimiter line, and a lone CR leaves it no delimiter, as for wenmode'

    def test_parse_markdown_frontmatter_with_trailing_whitespace_finds_the_block_wenmode_finds(self) -> None:
        #: Given
        texts = generate_texts(
            Variation(
                endings=('\n', '\r\n'), delimiter_tails=('', ' ', '\t', ' \t ', 'x', '-'), closing_probability=0.8
            )
        )

        #: When
        differing = disagreements(texts)

        #: Then
        assert differing == [], 'a delimiter takes trailing spaces and tabs, and nothing else'

    def test_parse_markdown_frontmatter_with_a_missing_closing_delimiter_finds_the_block_wenmode_finds(self) -> None:
        #: Given
        texts = generate_texts(Variation(endings=('\n', '\r\n'), closing_probability=0.3, later_delimiters=True))

        #: When
        differing = disagreements(texts)

        #: Then
        assert differing == [], 'a block closed by no delimiter of its own is closed by a later one, or by none'

    def test_parse_markdown_frontmatter_with_a_byte_order_mark_finds_the_block_wenmode_finds(self) -> None:
        #: Given
        texts = generate_texts(Variation(prefixes=('', BYTE_ORDER_MARK, ' '), closing_probability=0.8))

        #: When
        differing = disagreements(texts)

        #: Then
        assert differing == [], 'a first line that is not `---` from its first character opens no block'

    def test_parse_markdown_frontmatter_with_an_empty_block_finds_the_block_wenmode_finds(self) -> None:
        #: Given
        texts = generate_texts(Variation(endings=('\n', '\r\n'), block_sizes=(0,), closing_probability=0.8))

        #: When
        differing = disagreements(texts)

        #: Then
        assert differing == [], 'two delimiters with nothing between them are an empty block, as for wenmode'

    def test_parse_markdown_frontmatter_with_delimiters_later_in_the_body_finds_the_block_wenmode_finds(self) -> None:
        #: Given
        texts = generate_texts(Variation(block_sizes=(0, 1, 3), closing_probability=0.5, later_delimiters=True))

        #: When
        differing = disagreements(texts)

        #: Then
        assert differing == [], 'the first `---` after the opening one closes the block, whatever follows it'

    def test_parse_markdown_frontmatter_with_exotic_line_breaks_finds_the_block_wenmode_finds(self) -> None:
        #: Given
        texts = generate_texts(Variation(endings=('\n', '\x0b', '\x0c', '\x85', '\u2028'), closing_probability=0.8))

        #: When
        differing = disagreements(texts)

        #: Then
        assert differing == [], 'a line breaks where `str.splitlines` breaks it, as it does for wenmode'
