"""The token-count input, built from a database's queries for one decoded document.

The budgets come from the model's governance and the count from the `tokens` query, so the input is tested over a
database opened on an in-memory snapshot: governed by a corpus and a namespace budget, and ungoverned.
"""

from typing import Final

import pytest

from lorecraft.checks import Database, DocumentText
from lorecraft.checks.inputs import Ungoverned, build_token_count_input
from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.syntax import count_tokens
from lorecraft.rules.inputs import Budget, TokenCountInput
from lorecraft.vfs import Snapshot

TYPING: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-typing'))
"""A document of corpus `code` its `python` namespace governs too."""

TYPING_TEXT: Final[str] = '# Typing\n\nAnnotate every signature.\n'
"""The text of `TYPING`."""

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code-python.structure.json')
"""The `python` namespace structure specification."""


class CountingDatabase(Database):
    """A database that records each document whose tokens it is asked to count, then counts them as usual."""

    def __init__(self, snapshot: Snapshot) -> None:
        """Open the database on the snapshot, with nothing counted yet.

        Args:
            snapshot: The revision the database reads.
        """
        super().__init__(snapshot)
        self.counted: list[DocumentRef] = []

    def tokens(self, source: DocumentText) -> int:
        """Record the document, then count its tokens.

        Args:
            source: The decoded document whose tokens are counted, recorded by its ref first.
        """
        self.counted.append(source.ref)
        return super().tokens(source)


def _snapshot(corpus_spec: bytes, namespace_spec: bytes) -> Snapshot:
    """A snapshot of corpus `code`, with a `python` namespace, holding the one document `TYPING`.

    Args:
        corpus_spec: Bytes of the corpus structure specification.
        namespace_spec: Bytes of the `python` namespace structure specification.
    """
    return Snapshot.from_tree(
        {
            'docs': {
                '__meta__': {
                    'code.md': b'# Code\n',
                    'code.structure.json': corpus_spec,
                    'code-python.md': b'# Code Python\n',
                    'code-python.structure.json': namespace_spec,
                },
                'code': {'python-typing.md': TYPING_TEXT.encode()},
            }
        }
    )


def _document_text(database: Database, ref: DocumentRef) -> DocumentText:
    """The witness of a document the test wrote as UTF-8, as the database decodes it.

    Args:
        database: The database the document is decoded by.
        ref: A document whose bytes are UTF-8.
    """
    source = database.text(ref)
    assert isinstance(source, DocumentText), f'{ref.path} was written as UTF-8, so it decodes'
    return source


@pytest.mark.it
class TestBuildTokenCountInput:
    def test_build_token_count_input_with_two_budgets_holds_both_in_the_order_the_specifications_apply(self) -> None:
        #: Given
        database = Database(_snapshot(b'{"tokens": 40}', b'{"tokens": 12}'))
        source = _document_text(database, TYPING)

        #: When
        subject = build_token_count_input(database, source)

        #: Then
        assert subject == TokenCountInput(
            token_count=UnsignedInt(count_tokens(TYPING_TEXT)),
            budgets=(
                Budget(tokens=NonZeroUnsignedInt(40), spec=CORPUS_SPEC),
                Budget(tokens=NonZeroUnsignedInt(12), spec=NAMESPACE_SPEC),
            ),
        ), 'the corpus budget comes first, then the namespace one, each naming the specification that sets it'

    def test_build_token_count_input_with_a_specification_setting_no_budget_leaves_it_out(self) -> None:
        #: Given
        database = Database(_snapshot(b'{"empty_sections": "forbidden"}', b'{"tokens": 12}'))
        source = _document_text(database, TYPING)

        #: When
        subject = build_token_count_input(database, source)

        #: Then
        assert subject == TokenCountInput(
            token_count=UnsignedInt(count_tokens(TYPING_TEXT)),
            budgets=(Budget(tokens=NonZeroUnsignedInt(12), spec=NAMESPACE_SPEC),),
        ), 'a specification that sets no budget adds none'

    def test_build_token_count_input_with_no_budget_set_returns_ungoverned(self) -> None:
        #: Given
        database = Database(_snapshot(b'{"empty_sections": "forbidden"}', b'{"empty_sections": "forbidden"}'))
        source = _document_text(database, TYPING)

        #: When
        subject = build_token_count_input(database, source)

        #: Then
        assert subject == Ungoverned(), 'no specification sets a budget, so no budget governs the document'

    def test_build_token_count_input_with_no_budget_set_never_counts_the_tokens(self) -> None:
        #: Given
        database = CountingDatabase(_snapshot(b'{"empty_sections": "forbidden"}', b'{"empty_sections": "forbidden"}'))
        source = _document_text(database, TYPING)

        #: When
        build_token_count_input(database, source)

        #: Then
        assert database.counted == [], 'governance is read first, so an ungoverned document never pays for the count'
