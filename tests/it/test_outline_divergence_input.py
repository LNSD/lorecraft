"""The outline divergence input, and the `outline_divergences` query it is built from, for one decoded document.

The outlines come from the model's governance and the sections from the `parse` query, so both are tested over a
database opened on an in-memory snapshot: a document that follows its outline, one that diverges from it, one
governed by two specifications of which one states an outline, one no outline governs, and one in no corpus. How
each divergence is found is `match_outlines`'s, tested on its own beside it.
"""

from typing import Final

import pytest

from lorecraft.checks import Database, DocumentText
from lorecraft.checks.inputs import Ungoverned, build_outline_divergence_input
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.schemas import AbsentSection, DocumentEnd, OutlineDivergenceSpec, SectionName
from lorecraft.project.syntax import LineNumber, ParsedDocument
from lorecraft.rules.inputs import OutlineDivergenceInput
from lorecraft.vfs import Snapshot

TYPING: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-typing'))
"""A document of corpus `code` its `python` namespace governs too."""

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code-python.structure.json')
"""The `python` namespace structure specification."""

RULE_ASIDE_CHECKLIST: Final[str] = (
    '# Typing\n'
    '\n'
    '## Rule\n'
    '\n'
    'Annotate every signature.\n'
    '\n'
    '## Aside\n'
    '\n'
    'Read the rationale once.\n'
    '\n'
    '## Checklist\n'
    '\n'
    '- [ ] Annotated.\n'
)
"""A document of thirteen lines: a title, then the sections `Rule`, `Aside` and `Checklist`."""


class ParsingDatabase(Database):
    """A database that records each document it is asked to parse, then parses it as usual."""

    def __init__(self, snapshot: Snapshot) -> None:
        """Open the database on the snapshot, with nothing parsed yet.

        Args:
            snapshot: The revision the database reads.
        """
        super().__init__(snapshot)
        self.parsed: list[DocumentRef] = []

    def parse(self, source: DocumentText) -> ParsedDocument:
        """Record the document, then parse it.

        Args:
            source: The decoded document that is parsed, recorded by its ref first.
        """
        self.parsed.append(source.ref)
        return super().parse(source)


def _snapshot(corpus_spec: bytes | None, namespace_spec: bytes | None, text: str) -> Snapshot:
    """A snapshot of corpus `code`, with a `python` namespace, holding the one document `TYPING`.

    Args:
        corpus_spec: Bytes of the corpus structure specification, or `None` for a corpus that has none.
        namespace_spec: Bytes of the `python` namespace structure specification, or `None` for none.
        text: The text of `TYPING`.
    """
    meta: dict[str, bytes] = {'code.md': b'# Code\n', 'code-python.md': b'# Code Python\n'}
    if corpus_spec is not None:
        meta['code.structure.json'] = corpus_spec
    if namespace_spec is not None:
        meta['code-python.structure.json'] = namespace_spec
    return Snapshot.from_tree({'docs': {'__meta__': meta, 'code': {'python-typing.md': text.encode()}}})


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
class TestBuildOutlineDivergenceInput:
    def test_build_outline_divergence_input_with_a_document_following_its_outline_holds_no_divergence(self) -> None:
        #: Given
        outline = b'{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}]}'
        database = Database(_snapshot(outline, None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        subject = build_outline_divergence_input(database, source)

        #: Then
        assert subject == OutlineDivergenceInput(specs=(OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=None),)), (
            'a document whose sections match the outline, an unnamed one inside an `any` run, does not diverge'
        )

    def test_build_outline_divergence_input_with_two_specifications_holds_only_those_stating_an_outline(self) -> None:
        #: Given
        corpus_spec = b'{"empty_sections": "forbidden"}'
        namespace_spec = b'{"outline": [{"section": "Rule"}, {"any": true}]}'
        database = Database(_snapshot(corpus_spec, namespace_spec, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        subject = build_outline_divergence_input(database, source)

        #: Then
        assert subject == OutlineDivergenceInput(
            specs=(OutlineDivergenceSpec(spec=NAMESPACE_SPEC, divergence=None),)
        ), 'a specification that states no outline has no entry, and the one that does is matched on its own'

    def test_build_outline_divergence_input_with_no_outline_returns_ungoverned(self) -> None:
        #: Given
        database = Database(_snapshot(b'{"empty_sections": "forbidden"}', None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        subject = build_outline_divergence_input(database, source)

        #: Then
        assert subject == Ungoverned(), 'no structure specification states an outline, so no outline governs it'

    def test_build_outline_divergence_input_with_no_outline_never_parses_the_document(self) -> None:
        #: Given
        database = ParsingDatabase(_snapshot(b'{"empty_sections": "forbidden"}', None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        build_outline_divergence_input(database, source)

        #: Then
        assert database.parsed == [], 'governance is read first, so a document no outline governs is never parsed'

    def test_build_outline_divergence_input_with_a_document_in_no_corpus_returns_ungoverned(self) -> None:
        #: Given
        # the code corpus has an outline, but `docs/blog/` has no corpus spec, so the model holds no `blog` corpus
        snapshot = Snapshot.from_tree(
            {
                'docs': {
                    '__meta__': {'code.md': b'# Code\n', 'code.structure.json': b'{"outline": [{"section": "Rule"}]}'},
                    'blog': {'launch.md': b'# Launch\n'},
                }
            }
        )
        database = Database(snapshot)
        source = _document_text(database, DocumentRef(CorpusName.parse('blog'), AspectFilename.parse('launch')))

        #: When
        subject = build_outline_divergence_input(database, source)

        #: Then
        assert subject == Ungoverned(), 'no specification governs a document in no corpus the model holds'


@pytest.mark.it
class TestOutlineDivergences:
    def test_outline_divergences_with_a_section_absent_at_the_end_holds_the_document_last_line(self) -> None:
        #: Given
        outline = (
            b'{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}, {"section": "See Also"}]}'
        )
        database = Database(_snapshot(outline, None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        divergences = database.outline_divergences(source)

        #: Then
        absent = AbsentSection(
            name=SectionName.parse('See Also'),
            description=None,
            example=None,
            before=DocumentEnd(last_line=LineNumber.from_int(13)),
        )
        assert divergences == (OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=absent),), (
            "the sections come from the parse and the end from the line count, the document's last line"
        )

    def test_outline_divergences_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        outline = b'{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}]}'
        database = ParsingDatabase(_snapshot(outline, None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)
        first = database.outline_divergences(source)

        #: When
        second = database.outline_divergences(source)

        #: Then
        assert second is first, 'the outlines are matched once per database, then shared by every rule'
        assert database.parsed == [TYPING], 'the document is parsed once, for the first call'

    def test_outline_divergences_with_no_outline_holds_none(self) -> None:
        #: Given
        database = Database(_snapshot(b'{"empty_sections": "forbidden"}', None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        divergences = database.outline_divergences(source)

        #: Then
        assert divergences == (), 'no structure specification states an outline, so no outline is matched'

    def test_outline_divergences_with_no_outline_never_parses_the_document(self) -> None:
        #: Given
        database = ParsingDatabase(_snapshot(b'{"empty_sections": "forbidden"}', None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        database.outline_divergences(source)

        #: Then
        assert database.parsed == [], 'the outlines are read first, so a document no outline governs is never parsed'

    def test_outline_divergences_with_a_document_in_no_corpus_holds_none(self) -> None:
        #: Given
        # the code corpus has an outline, but `docs/blog/` has no corpus spec, so the model holds no `blog` corpus
        snapshot = Snapshot.from_tree(
            {
                'docs': {
                    '__meta__': {'code.md': b'# Code\n', 'code.structure.json': b'{"outline": [{"section": "Rule"}]}'},
                    'blog': {'launch.md': b'# Launch\n'},
                }
            }
        )
        database = Database(snapshot)
        source = _document_text(database, DocumentRef(CorpusName.parse('blog'), AspectFilename.parse('launch')))

        #: When
        divergences = database.outline_divergences(source)

        #: Then
        assert divergences == (), 'no specification governs a document in no corpus the model holds'
