"""The `outline_divergences` query, for one decoded document.

The outlines come from the model's governance and the sections from the `parse` query, so the query is tested over a
database opened on an in-memory snapshot: a document that diverges from its outline, one governed by two
specifications of which one states an outline, one no outline governs, and one in no corpus. How each divergence is
found is `match_outlines`'s, tested on its own beside it.
"""

from collections.abc import Callable
from typing import Final

import pytest

import lorecraft.project.schemas.outline_queries as outline_queries_module
from lib.tree import from_tree
from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.database import Database, ItemText, QueryRead
from lorecraft.project.document import DocumentRef
from lorecraft.project.item import MarkdownItemRef
from lorecraft.project.schemas import (
    AbsentSection,
    DocumentEnd,
    OutlineAlignmentSpec,
    OutlineDivergenceSpec,
    SectionName,
    StructureSpec,
    align_outlines,
    outline_alignment,
)
from lorecraft.project.syntax import (
    Heading,
    LineNumber,
    ParsedDocument,
    SectionHeading,
    parse_document,
    section_headings,
)
from lorecraft.project.workspace import WorkspaceModel
from lorecraft.rules.outline.__ruleset__ import outline_divergences
from lorecraft.vfs import Snapshot, VirtualFileSystem

TYPING: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-typing'))
"""A document of corpus `code` its `python` namespace governs too."""

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.spec.json')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code-python.spec.json')
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


def _counting(
    calls: list[int],
) -> Callable[[tuple[StructureSpec, ...], tuple[Heading, ...]], tuple[OutlineAlignmentSpec, ...]]:
    """`align_outlines`, recording one call for each time it is run.

    Args:
        calls: Receives a `1` per call.
    """

    def counted(
        structure_specs: tuple[StructureSpec, ...], headings: tuple[Heading, ...]
    ) -> tuple[OutlineAlignmentSpec, ...]:
        calls.append(1)
        return align_outlines(structure_specs, headings)

    return counted


class ParsingDatabase(Database):
    """A database that records each document it is asked to parse, then parses it as usual."""

    def __init__(self, fs: VirtualFileSystem, model: WorkspaceModel) -> None:
        """Build the database on the view, with nothing parsed yet.

        Args:
            fs: The view of the revision the database reads.
            model: The workspace model loaded through the view.
        """
        super().__init__(fs, model)
        self.parsed: list[MarkdownItemRef] = []

    def item_parse(self, source: ItemText) -> ParsedDocument:
        """Record the document, then parse it.

        Args:
            source: The decoded document that is parsed, recorded by its ref first.
        """
        self.parsed.append(source.ref)
        return super().item_parse(source)


def _snapshot(corpus_spec: bytes | None, namespace_spec: bytes | None, text: str) -> Snapshot:
    """A snapshot of corpus `code`, with a `python` namespace, holding the one document `TYPING`.

    Args:
        corpus_spec: Bytes of the corpus structure specification, or `None` for a corpus that has none.
        namespace_spec: Bytes of the `python` namespace structure specification, or `None` for none.
        text: The text of `TYPING`.
    """
    meta: dict[str, bytes] = {'code.md': b'# Code\n', 'code-python.md': b'# Code Python\n'}
    if corpus_spec is not None:
        meta['code.spec.json'] = corpus_spec
    if namespace_spec is not None:
        meta['code-python.spec.json'] = namespace_spec
    return from_tree({'docs': {'__meta__': meta, 'code': {'python-typing.md': text.encode()}}})


def _checklist_heading() -> SectionHeading:
    """The `Checklist` section of `RULE_ASIDE_CHECKLIST`, as the real parser reads it.

    Raises:
        AssertionError: If the document holds no such heading.
    """
    for section in section_headings(parse_document(RULE_ASIDE_CHECKLIST).headings):
        if section.text == 'Checklist':
            return section
    raise AssertionError('the document holds a `Checklist` section')


def _document_text(database: Database, ref: DocumentRef) -> ItemText:
    """The witness of a document the test wrote as UTF-8, as the database decodes it.

    Args:
        database: The database the document is decoded by.
        ref: A document whose bytes are UTF-8.
    """
    source = database.item_text(MarkdownItemRef(ref.path))
    assert isinstance(source, ItemText), f'{ref.path} was written as UTF-8, so it decodes'
    return source


@pytest.mark.it
class TestOutlineDivergences:
    def test_outline_divergences_with_a_section_absent_at_the_end_holds_the_document_last_line(self) -> None:
        #: Given
        outline = (
            b'{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}, {"section": "See Also"}]}'
        )
        database = Database.from_snapshot(_snapshot(outline, None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        divergences = database.query(outline_divergences, source.ref)

        #: Then
        absent = AbsentSection(
            name=SectionName.parse('See Also'),
            description=None,
            example=None,
            before=DocumentEnd(last_line=LineNumber(NonZeroUnsignedInt(13)), after=_checklist_heading()),
        )
        assert divergences == (OutlineDivergenceSpec(spec=CORPUS_SPEC, divergence=absent),), (
            "the sections come from the parse and the end from the line count, the document's last line"
        )

    def test_outline_divergences_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        outline = b'{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}]}'
        database = ParsingDatabase.from_snapshot(_snapshot(outline, None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)
        first = database.query(outline_divergences, source.ref)

        #: When
        second = database.query(outline_divergences, source.ref)

        #: Then
        assert second is first, 'the outlines are matched once per database, then shared by every rule'
        assert database.parsed == [MarkdownItemRef(TYPING.path)], 'the document is parsed once, for the first call'

    def test_outline_divergences_with_two_specifications_holds_only_those_stating_an_outline(self) -> None:
        #: Given
        corpus_spec = b'{"empty_sections": "forbidden"}'
        namespace_spec = b'{"outline": [{"section": "Rule"}, {"any": true}]}'
        database = Database.from_snapshot(_snapshot(corpus_spec, namespace_spec, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        divergences = database.query(outline_divergences, source.ref)

        #: Then
        assert divergences == (OutlineDivergenceSpec(spec=NAMESPACE_SPEC, divergence=None),), (
            'a specification that states no outline has no entry, and the one that does is matched on its own'
        )

    def test_outline_divergences_with_no_outline_holds_none(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'{"empty_sections": "forbidden"}', None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        divergences = database.query(outline_divergences, source.ref)

        #: Then
        assert divergences == (), 'no structure specification states an outline, so no outline is matched'

    def test_outline_divergences_with_no_structure_specification_never_parses_the_document(self) -> None:
        #: Given
        database = ParsingDatabase.from_snapshot(_snapshot(None, None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        database.query(outline_divergences, source.ref)

        #: Then
        assert database.parsed == [], 'the governance is read first, so a document nothing governs is never parsed'

    def test_outline_divergences_with_a_document_in_no_corpus_holds_none(self) -> None:
        #: Given
        # the code corpus has an outline, but `docs/blog/` has no corpus spec, so the model holds no `blog` corpus
        snapshot = from_tree(
            {
                'docs': {
                    '__meta__': {'code.md': b'# Code\n', 'code.spec.json': b'{"outline": [{"section": "Rule"}]}'},
                    'blog': {'launch.md': b'# Launch\n'},
                }
            }
        )
        database = Database.from_snapshot(snapshot)
        source = _document_text(database, DocumentRef(CorpusName.parse('blog'), AspectFilename.parse('launch')))

        #: When
        divergences = database.query(outline_divergences, source.ref)

        #: Then
        assert divergences == (), 'no specification governs a document in no corpus the model holds'

    def test_outline_divergences_query_reads_the_line_count_only_when_an_outline_is_stated(self) -> None:
        #: Given
        ref = MarkdownItemRef(TYPING.path)
        outlined = Database.from_snapshot(_snapshot(b'{"outline": [{"section": "Rule"}]}', None, RULE_ASIDE_CHECKLIST))
        unoutlined = Database.from_snapshot(_snapshot(b'{"empty_sections": "forbidden"}', None, RULE_ASIDE_CHECKLIST))

        #: When
        outlined.query(outline_divergences, ref)
        unoutlined.query(outline_divergences, ref)

        #: Then
        assert QueryRead('line_count', ref) in outlined.query_reads(outline_divergences, ref), (
            'the end of the document is counted'
        )
        assert QueryRead('line_count', ref) not in unoutlined.query_reads(outline_divergences, ref), (
            'no outline, no lines counted'
        )

    def test_outline_divergences_then_outline_alignment_aligns_the_document_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        outline = b'{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}]}'
        database = Database.from_snapshot(_snapshot(outline, None, RULE_ASIDE_CHECKLIST))
        ref = MarkdownItemRef(TYPING.path)
        aligned: list[int] = []
        monkeypatch.setattr(outline_queries_module, 'align_outlines', _counting(aligned))
        database.query(outline_divergences, ref)

        #: When
        database.query(outline_alignment, ref)

        #: Then
        assert aligned == [1], 'the divergences ask for the alignment, which the later query then finds held'

    def test_outline_alignment_then_outline_divergences_aligns_the_document_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        outline = b'{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}]}'
        database = Database.from_snapshot(_snapshot(outline, None, RULE_ASIDE_CHECKLIST))
        ref = MarkdownItemRef(TYPING.path)
        aligned: list[int] = []
        monkeypatch.setattr(outline_queries_module, 'align_outlines', _counting(aligned))
        database.query(outline_alignment, ref)

        #: When
        database.query(outline_divergences, ref)

        #: Then
        assert aligned == [1], 'the divergences are derived from the alignment already held, so it is computed once'
