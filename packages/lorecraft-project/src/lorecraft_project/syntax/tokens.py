"""How many tokens a text costs an agent that reads it, counted with OpenAI's ``o200k_base`` encoding.

No vendor publishes a local tokenizer for every agent, so one fixed encoding stands in for all of them: the count
is the same whichever agent reads the document, and a budget set in it means the same thing everywhere. The
encoding is exact for OpenAI's current models; other vendors' tokenizers count the same text differently, by a
factor that depends on the content, so no correction is applied.

The encoding's vocabulary, ``o200k_base.tiktoken``, ships beside this module, as OpenAI publishes it. tiktoken's
own loaders are not used: ``get_encoding`` downloads the vocabulary on first use, and ``load_tiktoken_bpe`` copies
even a local file into a cache directory. This module reads the file itself and builds the encoding from it, so
counting never touches the network or writes anywhere. The encoding is built once per process.
"""

import binascii
from functools import cache
from importlib.resources import files
from typing import Final

from tiktoken import Encoding

_VOCABULARY_FILE: Final[str] = 'o200k_base.tiktoken'
"""The vocabulary shipped beside this module: one ``<base64 token> <rank>`` line per token."""

# Copied from `o200k_base` in tiktoken's `tiktoken_ext/openai_public.py`, which exposes it only inside the function
# that downloads the vocabulary. It is how a text is split into words before the merges run, so it is part of the
# encoding as much as the vocabulary is.
_SPLIT_PATTERN: Final[str] = '|'.join(
    [
        r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]*[\p{Ll}\p{Lm}\p{Lo}\p{M}]+(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
        r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}]+[\p{Ll}\p{Lm}\p{Lo}\p{M}]*(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
        r"""\p{N}{1,3}""",
        r""" ?[^\s\p{L}\p{N}]+[\r\n/]*""",
        r"""\s*[\r\n]+""",
        r"""\s+(?!\S)""",
        r"""\s+""",
    ]
)


def count_tokens(text: str) -> int:
    """The number of ``o200k_base`` tokens in ``text``.

    Text that looks like a special token, such as ``<|endoftext|>``, is counted as the ordinary text it is: a
    document is never a prompt with control tokens in it.

    The first call in a process reads the shipped vocabulary and builds the encoding, about 100 ms; later calls
    reuse it.
    """
    return len(_encoding().encode_ordinary(text))


# Built once per process: the vocabulary is a file inside the installed package, so it cannot change while the
# process runs, and building the encoding from its 200,000 lines costs far more than counting a document does. The
# cached encoding is mutable, but it never leaves this module, so no caller can change the shared instance.
#
# The build costs ~100 ms: about half decodes the vocabulary, and the rest is tiktoken building its encoder, which
# no input format changes. The decode's time goes to per-line overhead on 200,000 tokens of ~10 characters, not to
# base64 itself, so a SIMD base64 decoder would not help; `_read_vocabulary` cuts the per-line work instead.
@cache
def _encoding() -> Encoding:
    """The ``o200k_base`` encoding, built from the vocabulary shipped beside this module."""
    # No special tokens: `count_tokens` encodes ordinary text only, so none could ever be produced.
    return Encoding('o200k_base', pat_str=_SPLIT_PATTERN, mergeable_ranks=_read_vocabulary(), special_tokens={})


def _read_vocabulary() -> dict[bytes, int]:
    """Every token of the shipped vocabulary, mapped to its rank."""
    vocabulary = files('lorecraft_project.syntax').joinpath(_VOCABULARY_FILE).read_bytes()
    ranks: dict[bytes, int] = {}
    # Two savings halve the decode. OpenAI writes each line's rank as its index, so the rank is counted rather than
    # parsed; the test suite pins the file's hash to OpenAI's, so the file cannot change under that assumption. And
    # `a2b_base64` is called directly, skipping the `base64.b64decode` wrapper.
    for rank, line in enumerate(vocabulary.splitlines()):
        token, _, _ = line.partition(b' ')
        ranks[binascii.a2b_base64(token)] = rank
    return ranks
