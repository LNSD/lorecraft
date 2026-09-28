"""The database over a hand-built snapshot: the model, each frontmatter and each parse tree are computed once.

Every snapshot here is built in memory with ``Snapshot.of_files``, so no case reads the disk: the database is
what wires the virtual view, the model loader and the parser together.
"""

from typing import Final

import pytest

from lorecraft.checks import Database
from lorecraft_project.aspect import AspectFilename
from lorecraft_project.corpus import CorpusName
from lorecraft_project.document import DocumentDecodeError, DocumentRef
from lorecraft_project.syntax import Frontmatter
from lorecraft_vfs import RootRelativePath, Snapshot

GUIDE: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('guide'))


def _snapshot(guide: bytes) -> Snapshot:
    """A snapshot of one ``code`` corpus, with a spec and a header schema, holding ``guide.md``."""
    return Snapshot.of_files(
        {
            RootRelativePath.parse('docs/__meta__/code.md'): b'# Code\n',
            RootRelativePath.parse('docs/__meta__/code.header.json'): b'{"type": "object"}',
            RootRelativePath.parse('docs/code/guide.md'): guide,
        }
    )


@pytest.mark.it
class TestDatabase:
    def test_model_from_a_snapshot_lists_the_documents_the_snapshot_holds(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))

        #: When
        model = database.model()

        #: Then
        assert model.documents() == (GUIDE,), 'the model is loaded from the snapshot alone'

    def test_model_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))
        first = database.model()

        #: When
        second = database.model()

        #: Then
        assert second is first, 'the model is loaded once per database, then cached'

    def test_frontmatter_of_a_listed_document_returns_its_decoded_block(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))

        #: When
        frontmatter = database.frontmatter(GUIDE)

        #: Then
        assert isinstance(frontmatter, Frontmatter), 'the snapshot bytes decode into a frontmatter node'
        assert frontmatter.data == {'name': 'guide'}, 'the frontmatter holds the snapshot content'

    def test_frontmatter_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))
        first = database.frontmatter(GUIDE)

        #: When
        second = database.frontmatter(GUIDE)

        #: Then
        assert second is first, 'a document frontmatter is decoded once per database, then shared by every check'

    def test_frontmatter_of_a_document_that_is_not_utf8_raises_document_decode_error(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "gu\xffide"\n---\n'))

        #: When
        with pytest.raises(DocumentDecodeError) as exc_info:
            database.frontmatter(GUIDE)

        #: Then
        assert exc_info.value.ref == GUIDE, 'the error names the document that could not be decoded'

    def test_parse_of_a_listed_document_returns_its_frontmatter(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))

        #: When
        document = database.parse(GUIDE)

        #: Then
        assert isinstance(document.frontmatter, Frontmatter), 'the snapshot bytes parse into a frontmatter node'
        assert document.frontmatter.data == {'name': 'guide'}, 'the parse tree holds the snapshot content'

    def test_parse_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))
        first = database.parse(GUIDE)

        #: When
        second = database.parse(GUIDE)

        #: Then
        assert second is first, 'a document is parsed once per database, then shared by every check'

    def test_parse_of_a_document_that_is_not_utf8_raises_document_decode_error(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "gu\xffide"\n---\n'))

        #: When
        with pytest.raises(DocumentDecodeError) as exc_info:
            database.parse(GUIDE)

        #: Then
        assert exc_info.value.ref == GUIDE, 'the error names the document that could not be decoded'
