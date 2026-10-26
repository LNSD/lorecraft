"""The document-fact queries of the database, for one governed document.

Each query is computed once per database, a fresh one included; a skill has no document facts.
"""

from pathlib import Path
from typing import Final

import pytest

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.database import Database, ItemText, PrimitiveRead, Read
from lorecraft.project.item import ItemRef, UnlistedItemError
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.link_target import DocumentLink
from lorecraft.project.query import (
    ItemPrimitives,
    item_base,
    item_corpus,
    item_name,
    item_parse,
    item_structure_specs,
    item_token_count,
    linked_paths,
)
from lorecraft.project.schemas import CorpusSpecName, SpecName, title_facts
from lorecraft.project.syntax import Anchor, LineNumber
from lorecraft.project.workspace.builtin import AGENT_SKILLS_SPEC_LAYER as SKILLS_LAYER
from lorecraft.rules.length.too_many_tokens import token_facts
from lorecraft.rules.link.extension_link import extension_link_facts
from lorecraft.rules.link.mutual_link import mutual_link_facts
from lorecraft.rules.link.queries import linked_documents
from lorecraft.rules.outline.empty_section import empty_section_facts
from lorecraft.vfs import Snapshot, take_snapshot

GUIDE_MORE: Final[ItemRef] = ItemRef(RootRelativePath.parse('docs/code/guide-more.md'))
GUIDE: Final[ItemRef] = ItemRef(RootRelativePath.parse('docs/code/guide.md'))
FEATURE: Final[ItemRef] = ItemRef(RootRelativePath.parse('docs/feat/a.md'))
OTHER_GUIDE: Final[ItemRef] = ItemRef(RootRelativePath.parse('docs/code/b.md'))
SKILL: Final[ItemRef] = ItemRef(RootRelativePath.parse('.agents/skills/review/SKILL.md'))
SPEC_PATH: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.spec.json')
SPEC_MD: Final[ItemRef] = ItemRef(RootRelativePath.parse('docs/__meta__/code-python.md'))
SPEC: Final[bytes] = b'{"tokens": 500, "title": {"words": 2}, "empty_sections": "forbidden"}'
TEXT: Final[bytes] = b'# A Long Title\n\n## Empty\n\n## Full\n\n[more](guide-more.md)\n[none](guide-none.md)\n'


def _snapshot(root: Path) -> Snapshot:
    """A scanned `code` corpus with a `guide` document linking its extension `guide-more.md`, and a skill.

    Args:
        root: The empty directory the repository is written to.
    """
    files = {
        'docs/__meta__/code.md': b'# Code\n',
        'docs/__meta__/code-python.md': b'# Python\n',
        'docs/__meta__/code.spec.json': SPEC,
        'docs/code/guide.md': TEXT,
        'docs/code/guide-more.md': b'# More\n',
        '.agents/skills/review/SKILL.md': b'---\nname: review\n---\n',
    }
    for name, content in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(content)
    return take_snapshot(root, SNAPSHOT_SCOPE)


def _decoded(database: Database) -> ItemText:
    """The witness of the guide, which the test wrote as UTF-8."""
    source = database.item_text(GUIDE)
    assert isinstance(source, ItemText), 'the guide decodes'
    return source


def _anchors(primitives: ItemPrimitives) -> frozenset[Anchor]:
    """The anchor of every heading of the item's parse."""
    return primitives.query(item_parse).anchors


def _item_name(primitives: ItemPrimitives) -> AspectFilename | SpecName | None:
    """The typed filename of the item."""
    return primitives.query(item_name)


def _item_corpus(primitives: ItemPrimitives) -> CorpusName | None:
    """The typed corpus of the item."""
    return primitives.query(item_corpus)


def _document_base(primitives: ItemPrimitives) -> AspectFilename | SpecName | None:
    """The typed name of the document or specification the item extends."""
    return primitives.query(item_base)


@pytest.mark.it
class TestMarkdownPrimitives:
    def test_anchors_with_a_document_returns_the_anchors_of_its_parse(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        anchors = database.query(_anchors, GUIDE)

        #: Then
        assert anchors == database.query(item_parse, _decoded(database).ref).anchors, "the anchors are the parse's own"
        assert len(anchors) == 3, 'the title and the two sections each take an anchor'

    def test_item_name_with_a_document_returns_its_typed_filename(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        name = database.query(_item_name, GUIDE)

        #: Then
        assert name == AspectFilename.parse('guide'), 'the filename stem is returned as its typed value'

    def test_item_corpus_with_a_document_returns_its_typed_corpus(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        corpus = database.query(_item_corpus, GUIDE)

        #: Then
        assert corpus == CorpusName.parse('code'), 'the corpus is returned as its typed value'

    def test_item_base_with_a_specification_returns_its_typed_spec_name(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        base = database.query(_document_base, SPEC_MD)

        #: Then
        assert base == CorpusSpecName(CorpusName.parse('code')), 'code-python extends the code specification'

    def test_document_base_with_an_extension_returns_the_document_its_name_continues(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        base = database.query(_document_base, GUIDE_MORE)

        #: Then
        assert base == AspectFilename.parse('guide'), 'guide-more continues guide, the document beside it'

    def test_document_base_with_a_document_no_other_precedes_returns_none(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        base = database.query(_document_base, GUIDE)

        #: Then
        assert base is None, 'guide continues no other name'

    def test_document_base_with_a_skill_returns_none(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        base = database.query(_document_base, SKILL)

        #: Then
        assert base is None, 'a skill extends no document'


@pytest.mark.it
class TestDocumentFactQueries:
    def test_item_title_facts_called_twice_returns_the_first_answer(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))
        first = database.query(title_facts, GUIDE)

        #: When
        second = database.query(title_facts, GUIDE)

        #: Then
        assert second is first, 'the checks are memoized'

    def test_item_title_facts_on_a_fresh_database_holds_the_checks_of_the_governing_specification(
        self, tmp_path: Path
    ) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        constraints = database.query(title_facts, GUIDE).constraints

        #: Then
        assert [c.spec for c in constraints] == [SPEC_PATH], 'the item is resolved by the query itself'

    def test_item_title_facts_of_an_unlisted_path_raises_unlisted_item_error(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When / Then
        with pytest.raises(UnlistedItemError):
            database.query(title_facts, ItemRef(RootRelativePath.parse('README.md')))

    def test_query_token_facts_holds_the_budget_and_counts_the_file(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        facts = database.query(token_facts, GUIDE)

        #: Then
        assert [(b.spec, b.tokens.value) for b in facts.budgets] == [(SPEC_PATH, 500)], 'the budget names its file'
        assert facts.count == database.query(item_token_count, _decoded(database).ref), 'the count is the file whole'
        assert database.query_reads(token_facts, GUIDE) == {
            Read(item_structure_specs, GUIDE),
            Read(PrimitiveRead.GOVERNANCE, GUIDE),
            Read(item_token_count, GUIDE),
            Read(PrimitiveRead.TEXT, GUIDE),
        }, 'derived carry-over names each primitive and the item read'

    def test_query_empty_section_facts_holds_the_forbidding_file_and_the_empty_section(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        facts = database.query(empty_section_facts, GUIDE)

        #: Then
        assert facts.specs == (SPEC_PATH,), 'the file that forbids empty sections'
        assert [e.heading.text for e in facts.empty] == ['Empty'], 'the one empty section'
        assert database.query(empty_section_facts, GUIDE) is facts, 'the answer is memoized'

    def test_query_of_an_unlisted_path_raises_unlisted_item_error(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When / Then
        with pytest.raises(UnlistedItemError):
            database.query(token_facts, ItemRef(RootRelativePath.parse('README.md')))

    def test_query_extension_link_facts_holds_the_link_to_the_existing_extension_only(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        facts = database.query(extension_link_facts, GUIDE)

        #: Then
        assert facts.base == 'guide.md', 'the document that holds the links'
        assert [(link.line.value, link.extension) for link in facts.links] == [(7, 'guide-more.md')], 'the existing one'
        assert database.query(extension_link_facts, GUIDE) is facts, 'the answer is memoized'
        assert database.query_reads(extension_link_facts, GUIDE) == {
            Read(item_parse, GUIDE),
            Read(PrimitiveRead.TEXT, GUIDE),
            Read(PrimitiveRead.LINK_TARGETS, GUIDE),
            Read(PrimitiveRead.LINK_BASE, GUIDE),
            Read(item_name, GUIDE),
            Read(PrimitiveRead.DESCRIPTOR, GUIDE),
        }, 'derived carry-over'

    def test_query_extension_link_facts_of_a_skill_entry_holds_no_link(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        facts = database.query(extension_link_facts, SKILL)

        #: Then
        assert facts.links == (), 'a skill is no document'


@pytest.mark.it
class TestDocumentFactReads:
    def test_query_reads_only_the_primitives_the_query_names(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        database.query(title_facts, GUIDE)

        #: Then
        assert database.query_reads(title_facts, GUIDE) == {
            Read(item_structure_specs, GUIDE),
            Read(PrimitiveRead.GOVERNANCE, GUIDE),
            Read(item_parse, GUIDE),
            Read(PrimitiveRead.TEXT, GUIDE),
        }, 'the carry-over names each primitive and the item read'


def _document_links(primitives: ItemPrimitives) -> tuple[DocumentLink, ...]:
    """The links to another document the item holds."""
    return primitives.query(linked_documents)


@pytest.mark.it
class TestDocumentLinks:
    @staticmethod
    def _snapshot(root: Path) -> Snapshot:
        """A `code` guide linking a `feat` document that links back, a `code` one that does not, and a non-document."""
        files = {
            'docs/__meta__/code.md': b'# Code\n',
            'docs/code/guide.md': b'# Guide\n\n[a](../feat/a.md)\n[b](b.md)\n[r](../../README.md)\n[gone](gone.md)\n',
            'docs/feat/a.md': b'# A\n\n[back](../code/guide.md)\n',
            'docs/code/b.md': b'# B\n',
            'README.md': b'# Readme\n',
        }
        for name, content in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_bytes(content)
        return take_snapshot(root, SNAPSHOT_SCOPE)

    def test_document_links_holds_each_linked_document_with_its_corpus_and_back_link(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(self._snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        links = database.query(_document_links, GUIDE)

        #: Then
        assert links == (
            DocumentLink(
                line=LineNumber(NonZeroUnsignedInt(3)),
                url='../feat/a.md',
                corpus=CorpusName.parse('feat'),
                filename=AspectFilename.parse('a'),
                has_back_link=True,
            ),
            DocumentLink(
                line=LineNumber(NonZeroUnsignedInt(4)),
                url='b.md',
                corpus=CorpusName.parse('code'),
                filename=AspectFilename.parse('b'),
                has_back_link=False,
            ),
        ), 'existing documents only, README and the missing file left out, each with its url and back link'

    def test_document_links_called_twice_returns_the_first_answer(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(self._snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))
        first = database.query(_document_links, GUIDE)

        #: When
        second = database.query(_document_links, GUIDE)

        #: Then
        assert second is first, 'the links are memoized'

    def test_document_links_of_a_skill_entry_holds_none(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        links = database.query(_document_links, SKILL)

        #: Then
        assert links == (), 'a skill links to no document of the layout'

    def test_mutual_link_facts_holds_the_corpus_and_reads_only_what_it_names(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(self._snapshot(tmp_path), builtin_layers=(SKILLS_LAYER,))

        #: When
        facts = database.query(mutual_link_facts, GUIDE)

        #: Then
        assert facts.corpus == CorpusName.parse('code'), 'the corpus of the document'
        assert database.query_reads(mutual_link_facts, GUIDE) == {
            Read(item_corpus, GUIDE),
            Read(PrimitiveRead.TEXT, GUIDE),
            Read(item_name, GUIDE),
            Read(PrimitiveRead.LINK_BASE, GUIDE),
            Read(item_parse, GUIDE),
            Read(PrimitiveRead.LINK_TARGETS, GUIDE),
            Read(linked_documents, GUIDE),
            Read(linked_paths, GUIDE),
            Read(linked_paths, FEATURE),
            Read(item_parse, FEATURE),
            Read(PrimitiveRead.TEXT, FEATURE),
            Read(linked_paths, OTHER_GUIDE),
            Read(item_parse, OTHER_GUIDE),
            Read(PrimitiveRead.TEXT, OTHER_GUIDE),
            Read(PrimitiveRead.DESCRIPTOR, GUIDE),
            Read(PrimitiveRead.DESCRIPTOR, FEATURE),
            Read(PrimitiveRead.DESCRIPTOR, OTHER_GUIDE),
        } | {
            Read(primitive, ref)
            for ref in (FEATURE, OTHER_GUIDE)
            for primitive in (PrimitiveRead.LINK_BASE, PrimitiveRead.LINK_TARGETS)
        }, 'the carry-over includes dependencies of linked item queries'
