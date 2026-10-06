"""The headings input, built from a database's queries for one decoded document.

The structure specifications come from the model's governance and the headings from the `parse` query, so the
input is tested over a database opened on an in-memory snapshot: governed by a corpus and a namespace
specification, governed by an outline whose caps each section resolves, governed by caps on the title's words and
patterns on its text, and ungoverned.
"""

from typing import Final

import pytest

from lorecraft.checks import Database, DocumentText
from lorecraft.checks.inputs import Ungoverned, build_headings_input
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.schemas import SectionName
from lorecraft.project.syntax import Heading, ParsedDocument, parse_document
from lorecraft.rules.inputs import HeadingsInput, HeadingsSpec, SectionCap, TitleCap, TitleMismatch
from lorecraft.vfs import Snapshot

TYPING: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-typing'))
"""A document of corpus `code` its `python` namespace governs too."""

TYPING_TEXT: Final[str] = (
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
"""The text of `TYPING`: a title, then the sections `Rule`, `Aside` and `Checklist`."""

TYPING_HEADINGS: Final[tuple[Heading, ...]] = parse_document(TYPING_TEXT).headings
"""The headings of `TYPING`, as the parser reads them: the title, then its three sections."""

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code-python.structure.json')
"""The `python` namespace structure specification."""


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


def _snapshot(corpus_spec: bytes | None, namespace_spec: bytes | None, *, typing_text: str = TYPING_TEXT) -> Snapshot:
    """A snapshot of corpus `code`, with a `python` namespace, holding the one document `TYPING`.

    Args:
        corpus_spec: Bytes of the corpus structure specification, or `None` for a corpus that has none.
        namespace_spec: Bytes of the `python` namespace structure specification, or `None` for none.
        typing_text: The text of `TYPING`; `TYPING_TEXT` unless a test needs other headings.
    """
    meta: dict[str, bytes] = {'code.md': b'# Code\n', 'code-python.md': b'# Code Python\n'}
    if corpus_spec is not None:
        meta['code.structure.json'] = corpus_spec
    if namespace_spec is not None:
        meta['code-python.structure.json'] = namespace_spec
    return Snapshot.from_tree({'docs': {'__meta__': meta, 'code': {'python-typing.md': typing_text.encode()}}})


def _document_text(database: Database, ref: DocumentRef) -> DocumentText:
    """The witness of a document the test wrote as UTF-8, as the database decodes it.

    Args:
        database: The database the document is decoded by.
        ref: A document whose bytes are UTF-8.
    """
    source = database.text(ref)
    assert isinstance(source, DocumentText), f'{ref.path} was written as UTF-8, so it decodes'
    return source


def _section(text: str) -> Heading:
    """The H2 section of `TYPING` with this heading text.

    Args:
        text: The section's heading text.
    """
    for heading in TYPING_HEADINGS:
        if heading.level == 2 and heading.text == text:
            return heading
    raise AssertionError(f'`TYPING` holds a section `{text}`')


@pytest.mark.it
class TestBuildHeadingsInput:
    def test_build_headings_input_with_two_specifications_holds_each_in_the_order_they_apply(self) -> None:
        #: Given
        corpus_spec = b'{"empty_sections": "forbidden"}'
        namespace_spec = b'{"forbidden": ["Notes", "Todo"]}'
        database = Database(_snapshot(corpus_spec, namespace_spec))
        source = _document_text(database, TYPING)

        #: When
        subject = build_headings_input(database, source)

        #: Then
        assert subject == HeadingsInput(
            headings=TYPING_HEADINGS,
            corpus=HeadingsSpec(
                spec=CORPUS_SPEC,
                title_cap=None,
                title_mismatch=None,
                forbid_empty_sections=True,
                forbidden=(),
                section_caps=(),
            ),
            namespaces=(
                HeadingsSpec(
                    spec=NAMESPACE_SPEC,
                    title_cap=None,
                    title_mismatch=None,
                    forbid_empty_sections=False,
                    forbidden=(SectionName.parse('Notes'), SectionName.parse('Todo')),
                    section_caps=(),
                ),
            ),
        ), (
            'the corpus specification is held apart for the title rules and comes first, then the namespace one, '
            'each with what it states on its own'
        )

    def test_build_headings_input_with_an_outline_resolves_each_section_cap(self) -> None:
        #: Given
        # `Rule` takes its entry's cap, `Aside` the cap of the `any` run it falls in, and `Checklist` none
        outline = (
            b'{"outline": [{"section": "Rule", "words": 40}, {"any": true, "words": 25}, {"section": "Checklist"}]}'
        )
        database = Database(_snapshot(outline, None))
        source = _document_text(database, TYPING)

        #: When
        subject = build_headings_input(database, source)

        #: Then
        assert subject == HeadingsInput(
            headings=TYPING_HEADINGS,
            corpus=HeadingsSpec(
                spec=CORPUS_SPEC,
                title_cap=None,
                title_mismatch=None,
                forbid_empty_sections=False,
                forbidden=(),
                section_caps=(
                    SectionCap(section=_section('Rule'), words=NonZeroUnsignedInt(40)),
                    SectionCap(section=_section('Aside'), words=NonZeroUnsignedInt(25)),
                ),
            ),
            namespaces=(),
        ), 'a named section takes its entry cap, an unnamed one its run cap, and a section with no cap is left out'

    def test_build_headings_input_with_title_word_caps_holds_each_against_the_first_title(self) -> None:
        #: Given
        typing_text = '# Typing in Python\n\nAnnotate every signature.\n\n# Typing again\n'
        database = Database(_snapshot(b'{"title": {"words": 2}}', b'{"title": {"words": 5}}', typing_text=typing_text))
        source = _document_text(database, TYPING)

        #: When
        subject = build_headings_input(database, source)

        #: Then
        headings = parse_document(typing_text).headings
        assert subject == HeadingsInput(
            headings=headings,
            corpus=HeadingsSpec(
                spec=CORPUS_SPEC,
                title_cap=TitleCap(title=headings[0], title_words=3, words=NonZeroUnsignedInt(2)),
                title_mismatch=None,
                forbid_empty_sections=False,
                forbidden=(),
                section_caps=(),
            ),
            namespaces=(
                HeadingsSpec(
                    spec=NAMESPACE_SPEC,
                    title_cap=TitleCap(title=headings[0], title_words=3, words=NonZeroUnsignedInt(5)),
                    title_mismatch=None,
                    forbid_empty_sections=False,
                    forbidden=(),
                    section_caps=(),
                ),
            ),
        ), 'each specification holds its own cap against the first H1 alone, with the words of its own text'

    def test_build_headings_input_with_a_title_word_cap_and_no_title_holds_no_title_cap(self) -> None:
        #: Given
        typing_text = '## Rule\n\nAnnotate every signature.\n'
        database = Database(_snapshot(b'{"title": {"words": 2}}', None, typing_text=typing_text))
        source = _document_text(database, TYPING)

        #: When
        subject = build_headings_input(database, source)

        #: Then
        assert isinstance(subject, HeadingsInput), 'a structure specification governs the document'
        assert subject.corpus.title_cap is None, 'a document with no title has no title to hold to a cap'

    def test_build_headings_input_with_a_title_pattern_the_first_title_fails_holds_the_mismatch(self) -> None:
        #: Given
        typing_text = '# typing in Python\n\nAnnotate every signature.\n\n# Typing again\n'
        database = Database(
            _snapshot(b'{"title": {"pattern": "^[A-Z]"}}', b'{"title": {"pattern": "Python"}}', typing_text=typing_text)
        )
        source = _document_text(database, TYPING)

        #: When
        subject = build_headings_input(database, source)

        #: Then
        headings = parse_document(typing_text).headings
        assert subject == HeadingsInput(
            headings=headings,
            corpus=HeadingsSpec(
                spec=CORPUS_SPEC,
                title_cap=None,
                title_mismatch=TitleMismatch(title=headings[0], pattern='^[A-Z]'),
                forbid_empty_sections=False,
                forbidden=(),
                section_caps=(),
            ),
            namespaces=(
                HeadingsSpec(
                    spec=NAMESPACE_SPEC,
                    title_cap=None,
                    title_mismatch=None,
                    forbid_empty_sections=False,
                    forbidden=(),
                    section_caps=(),
                ),
            ),
        ), (
            'each specification matches its own pattern against the first H1 alone: the corpus pattern fails it, '
            'though the later H1 would match, and the namespace pattern is found inside it'
        )

    def test_build_headings_input_with_a_title_pattern_the_first_title_matches_holds_no_mismatch(self) -> None:
        #: Given
        typing_text = '# Typing in Python\n\nAnnotate every signature.\n\n# typing again\n'
        database = Database(_snapshot(b'{"title": {"pattern": "^[A-Z]"}}', None, typing_text=typing_text))
        source = _document_text(database, TYPING)

        #: When
        subject = build_headings_input(database, source)

        #: Then
        assert isinstance(subject, HeadingsInput), 'a structure specification governs the document'
        assert subject.corpus.title_mismatch is None, (
            'a first title that matches is no mismatch, though a later H1 would fail the pattern'
        )

    def test_build_headings_input_with_a_title_pattern_and_no_title_holds_no_mismatch(self) -> None:
        #: Given
        typing_text = '## Rule\n\nAnnotate every signature.\n'
        database = Database(_snapshot(b'{"title": {"pattern": "^[A-Z]"}}', None, typing_text=typing_text))
        source = _document_text(database, TYPING)

        #: When
        subject = build_headings_input(database, source)

        #: Then
        assert isinstance(subject, HeadingsInput), 'a structure specification governs the document'
        assert subject.corpus.title_mismatch is None, 'a document with no title has no title to hold to a pattern'

    def test_build_headings_input_with_no_structure_specification_returns_ungoverned(self) -> None:
        #: Given
        database = Database(_snapshot(None, None))
        source = _document_text(database, TYPING)

        #: When
        subject = build_headings_input(database, source)

        #: Then
        assert subject == Ungoverned(), 'no structure specification governs the document, so its headings are not'

    def test_build_headings_input_with_no_structure_specification_never_parses_the_document(self) -> None:
        #: Given
        database = ParsingDatabase(_snapshot(None, None))
        source = _document_text(database, TYPING)

        #: When
        build_headings_input(database, source)

        #: Then
        assert database.parsed == [], 'governance is read first, so an ungoverned document is never parsed'

    def test_build_headings_input_with_a_document_in_no_corpus_returns_ungoverned(self) -> None:
        #: Given
        # the code corpus has a structure specification, but `docs/blog/` has no corpus spec, so the model holds no
        # `blog` corpus
        snapshot = Snapshot.from_tree(
            {
                'docs': {
                    '__meta__': {'code.md': b'# Code\n', 'code.structure.json': b'{"empty_sections": "forbidden"}'},
                    'blog': {'launch.md': b'# Launch\n'},
                }
            }
        )
        database = Database(snapshot)
        source = _document_text(database, DocumentRef(CorpusName.parse('blog'), AspectFilename.parse('launch')))

        #: When
        subject = build_headings_input(database, source)

        #: Then
        assert subject == Ungoverned(), 'no specification governs a document in no corpus the model holds'
