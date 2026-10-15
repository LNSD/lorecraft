"""The `outline_alignment` query, for one decoded document.

The specifications come from the model's governance and the sections from the `parse` query, so the query is tested
over a database opened on an in-memory snapshot: a document governed by an outline, one governed by two
specifications of which one states no outline, one no structure specification governs, and one in no corpus. How a
section is aligned is `align_outlines`'s, tested on its own beside it.
"""

from collections.abc import Callable
from typing import Final

import pytest

import lorecraft.project.database.database as database_module
from lib.tree import from_tree
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.database import Database, DocumentText
from lorecraft.project.document import DocumentRef
from lorecraft.project.schemas import (
    AnyRunAlignment,
    NamedAlignment,
    OutlineAlignmentSpec,
    StructureSpec,
    UnalignedSection,
    align_outlines,
)
from lorecraft.project.schemas.outline_alignment import AlignedSection
from lorecraft.project.syntax import Heading, ParsedDocument
from lorecraft.project.workspace import WorkspaceModel
from lorecraft.vfs import Snapshot, VirtualFileSystem

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

    def __init__(self, fs: VirtualFileSystem, model: WorkspaceModel) -> None:
        """Build the database on the view, with nothing parsed yet.

        Args:
            fs: The view of the revision the database reads.
            model: The workspace model loaded through the view.
        """
        super().__init__(fs, model)
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
    return from_tree({'docs': {'__meta__': meta, 'code': {'python-typing.md': text.encode()}}})


def _document_text(database: Database, ref: DocumentRef) -> DocumentText:
    """The witness of a document the test wrote as UTF-8, as the database decodes it.

    Args:
        database: The database the document is decoded by.
        ref: A document whose bytes are UTF-8.
    """
    source = database.text(ref)
    assert isinstance(source, DocumentText), f'{ref.path} was written as UTF-8, so it decodes'
    return source


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


def _specs(alignment: tuple[OutlineAlignmentSpec, ...]) -> list[RootRelativePath]:
    """The structure specification file each part of an outline alignment belongs to, in the order given.

    Args:
        alignment: What `outline_alignment` returned, one part per governing specification.
    """
    return [aligned.spec for aligned in alignment]


def _section_types(sections: tuple[AlignedSection, ...]) -> list[type[AlignedSection]]:
    """The alignment kind of each section, in document order.

    Args:
        sections: Sections of one specification's alignment.
    """
    return [type(aligned) for aligned in sections]


def _forbidden_flags(sections: tuple[AlignedSection, ...]) -> list[bool]:
    """Whether each unaligned section is one the specification forbids, in document order.

    Args:
        sections: Sections of one specification's alignment; the aligned ones are left out.
    """
    return [aligned.forbidden for aligned in sections if isinstance(aligned, UnalignedSection)]


@pytest.mark.it
class TestOutlineAlignment:
    def test_outline_alignment_with_an_outlined_document_aligns_each_section_to_its_entry(self) -> None:
        #: Given
        outline = b'{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}]}'
        database = Database.from_snapshot(_snapshot(outline, None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        alignment = database.outline_alignment(source)

        #: Then
        assert len(alignment) == 1, 'the one governing specification is aligned'
        assert alignment[0].spec == CORPUS_SPEC, 'it is the corpus specification'
        sections = alignment[0].sections
        assert _section_types(sections) == [
            NamedAlignment,
            AnyRunAlignment,
            NamedAlignment,
        ], 'the sections are read from the parse: `Rule` and `Checklist` by name, `Aside` by the `any` run'

    def test_outline_alignment_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        outline = b'{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}]}'
        database = ParsingDatabase.from_snapshot(_snapshot(outline, None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)
        first = database.outline_alignment(source)

        #: When
        second = database.outline_alignment(source)

        #: Then
        assert second is first, 'the sections are aligned once per database, then shared by every rule'
        assert database.parsed == [TYPING], 'the document is parsed once, for the first call'

    def test_outline_alignment_with_a_specification_stating_no_outline_aligns_it_to_nothing(self) -> None:
        #: Given
        corpus_spec = b'{"forbidden": ["Aside"]}'
        namespace_spec = b'{"outline": [{"section": "Rule"}, {"any": true}]}'
        database = Database.from_snapshot(_snapshot(corpus_spec, namespace_spec, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        alignment = database.outline_alignment(source)

        #: Then
        assert len(alignment) == 2, 'both specifications are aligned'
        assert _specs(alignment) == [CORPUS_SPEC, NAMESPACE_SPEC], (
            'a specification that states no outline is aligned too, for the sections it forbids'
        )
        corpus_sections = alignment[0].sections
        assert _section_types(corpus_sections) == [UnalignedSection] * 3, 'it has no entry to align to'
        assert _forbidden_flags(corpus_sections) == [
            False,
            True,
            False,
        ], 'it still marks the section it forbids'

    def test_outline_alignment_with_no_structure_specification_holds_none(self) -> None:
        #: Given
        database = ParsingDatabase.from_snapshot(_snapshot(None, None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)

        #: When
        alignment = database.outline_alignment(source)

        #: Then
        assert alignment == (), 'no structure specification governs the document, so nothing is aligned'
        assert database.parsed == [], 'the specifications are read first, so an ungoverned document is never parsed'

    def test_outline_alignment_with_a_document_in_no_corpus_holds_none(self) -> None:
        #: Given
        # the code corpus has an outline, but `docs/blog/` has no corpus spec, so the model holds no `blog` corpus
        snapshot = from_tree(
            {
                'docs': {
                    '__meta__': {'code.md': b'# Code\n', 'code.structure.json': b'{"outline": [{"section": "Rule"}]}'},
                    'blog': {'launch.md': b'# Launch\n'},
                }
            }
        )
        database = Database.from_snapshot(snapshot)
        source = _document_text(database, DocumentRef(CorpusName.parse('blog'), AspectFilename.parse('launch')))

        #: When
        alignment = database.outline_alignment(source)

        #: Then
        assert alignment == (), 'no specification governs a document in no corpus the model holds'

    def test_outline_alignment_then_outline_divergences_aligns_the_document_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        outline = b'{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}]}'
        database = Database.from_snapshot(_snapshot(outline, None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)
        aligned: list[int] = []
        monkeypatch.setattr(database_module, 'align_outlines', _counting(aligned))
        database.outline_alignment(source)

        #: When
        database.outline_divergences(source)

        #: Then
        assert aligned == [1], 'the divergences are derived from the alignment already held, so it is computed once'

    def test_outline_divergences_then_outline_alignment_aligns_the_document_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #: Given
        outline = b'{"outline": [{"section": "Rule"}, {"any": true}, {"section": "Checklist"}]}'
        database = Database.from_snapshot(_snapshot(outline, None, RULE_ASIDE_CHECKLIST))
        source = _document_text(database, TYPING)
        aligned: list[int] = []
        monkeypatch.setattr(database_module, 'align_outlines', _counting(aligned))
        database.outline_divergences(source)

        #: When
        database.outline_alignment(source)

        #: Then
        assert aligned == [1], 'the divergences ask for the alignment, which the later query then finds held'
