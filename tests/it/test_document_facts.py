"""The document-fact queries of the database and the context methods over them, for one governed document.

Each query is computed once per database, a fresh one included; the context refuses a skill entry.
"""

from pathlib import Path
from typing import Final

import pytest

from lorecraft.core.num import NonZeroUnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import Database, DatabaseItemContext, ItemText
from lorecraft.project.database.context import WrongItemKindError
from lorecraft.project.item import MarkdownItemRef, UnlistedItemError
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.link_target import DocumentLink
from lorecraft.project.schemas import title_facts
from lorecraft.project.syntax import LineNumber
from lorecraft.rules.length.too_many_tokens import token_facts
from lorecraft.rules.outline.empty_section import empty_section_facts
from lorecraft.vfs import Snapshot, take_snapshot

GUIDE: Final[MarkdownItemRef] = MarkdownItemRef(RootRelativePath.parse('docs/code/guide.md'))
SKILL: Final[MarkdownItemRef] = MarkdownItemRef(RootRelativePath.parse('.agents/skills/review/SKILL.md'))
SPEC_PATH: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.spec.json')
SPEC: Final[bytes] = b'{"tokens": 500, "title": {"words": 2}, "empty_sections": "forbidden"}'
TEXT: Final[bytes] = b'# A Long Title\n\n## Empty\n\n## Full\n\n[more](guide-more.md)\n[none](guide-none.md)\n'


def _snapshot(root: Path) -> Snapshot:
    """A scanned `code` corpus with a `guide` document linking its extension `guide-more.md`, and a skill.

    Args:
        root: The empty directory the repository is written to.
    """
    files = {
        'docs/__meta__/code.md': b'# Code\n',
        'docs/__meta__/code.spec.json': SPEC,
        'docs/code/guide.md': TEXT,
        'docs/code/guide-more.md': b'# More\n',
        '.agents/skills/review/SKILL.md': b'---\nname: review\n---\n',
    }
    for name, content in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(content)
    return take_snapshot(root, SNAPSHOT_SCOPE)


def _context(database: Database, ref: MarkdownItemRef) -> DatabaseItemContext:
    """The context of an item the test wrote as UTF-8."""
    source = database.item_text(ref)
    assert isinstance(source, ItemText), f'{ref.path} was written as UTF-8, so it decodes'
    return DatabaseItemContext(database, source)


def _decoded(database: Database) -> ItemText:
    """The witness of the guide, which the test wrote as UTF-8."""
    source = database.item_text(GUIDE)
    assert isinstance(source, ItemText), 'the guide decodes'
    return source


@pytest.mark.it
class TestDocumentFactQueries:
    def test_item_title_called_twice_returns_the_first_answer(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))
        source = _decoded(database)
        first = database.item_title(source)

        #: When
        second = database.item_title(source)

        #: Then
        assert second is first, 'the title is memoized'

    def test_item_title_facts_called_twice_returns_the_first_answer(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))
        first = database.query(title_facts, GUIDE)

        #: When
        second = database.query(title_facts, GUIDE)

        #: Then
        assert second is first, 'the checks are memoized'

    def test_item_title_facts_on_a_fresh_database_holds_the_checks_of_the_governing_specification(
        self, tmp_path: Path
    ) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))

        #: When
        constraints = database.query(title_facts, GUIDE).constraints

        #: Then
        assert [c.spec for c in constraints] == [SPEC_PATH], 'the item is resolved by the query itself'

    def test_item_title_facts_of_an_unlisted_path_raises_unlisted_item_error(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))

        #: When / Then
        with pytest.raises(UnlistedItemError):
            database.query(title_facts, MarkdownItemRef(RootRelativePath.parse('README.md')))

    def test_query_token_facts_holds_the_budget_and_counts_the_file(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))

        #: When
        facts = database.query(token_facts, GUIDE)

        #: Then
        assert [(b.spec, b.tokens.value) for b in facts.budgets] == [(SPEC_PATH, 500)], 'the budget names its file'
        assert facts.count == database.item_token_count(_decoded(database)), 'the count is the file whole'
        assert database.query_reads(token_facts, GUIDE) == {'structure_specs', 'token_count'}, 'derived carry-over'

    def test_query_empty_section_facts_holds_the_forbidding_file_and_the_empty_section(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))

        #: When
        facts = database.query(empty_section_facts, GUIDE)

        #: Then
        assert facts.specs == (SPEC_PATH,), 'the file that forbids empty sections'
        assert [e.heading.text for e in facts.empty] == ['Empty'], 'the one empty section'
        assert database.query(empty_section_facts, GUIDE) is facts, 'the answer is memoized'

    def test_query_of_an_unlisted_path_raises_unlisted_item_error(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))

        #: When / Then
        with pytest.raises(UnlistedItemError):
            database.query(token_facts, MarkdownItemRef(RootRelativePath.parse('README.md')))

    def test_item_extension_links_called_twice_returns_the_first_answer(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))
        source = _decoded(database)
        first = database.item_extension_links(source)

        #: When
        second = database.item_extension_links(source)

        #: Then
        assert second is first, 'the links are memoized'


@pytest.mark.it
class TestDocumentFactContext:
    def test_title_measures_the_title_of_the_document(self, tmp_path: Path) -> None:
        #: Given
        context = _context(Database.from_snapshot(_snapshot(tmp_path)), GUIDE)

        #: When
        title = context.title()

        #: Then
        assert title is not None, 'the document has a title'
        assert (title.chars.value, title.words.value) == (12, 3), 'the title is measured'

    def test_query_reads_only_the_primitives_the_query_names(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))

        #: When
        database.query(title_facts, GUIDE)

        #: Then
        assert database.query_reads(title_facts, GUIDE) == {'structure_specs', 'headings'}, 'the carry-over is derived'

    def test_title_of_a_skill_entry_raises_wrong_item_kind_error(self, tmp_path: Path) -> None:
        #: Given
        context = _context(Database.from_snapshot(_snapshot(tmp_path)), SKILL)

        #: When / Then
        with pytest.raises(WrongItemKindError):
            context.title()

    def test_extension_links_holds_the_link_to_the_existing_extension_only(self, tmp_path: Path) -> None:
        #: Given
        context = _context(Database.from_snapshot(_snapshot(tmp_path)), GUIDE)

        #: When
        links = context.extension_links()

        #: Then
        assert [(link.line.value, link.extension) for link in links] == [(7, 'guide-more.md')], 'the existing one'

    def test_extension_links_of_a_skill_entry_raises_wrong_item_kind_error(self, tmp_path: Path) -> None:
        #: Given
        context = _context(Database.from_snapshot(_snapshot(tmp_path)), SKILL)

        #: When / Then
        with pytest.raises(WrongItemKindError):
            context.extension_links()


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
        context = _context(Database.from_snapshot(self._snapshot(tmp_path)), GUIDE)

        #: When
        links = context.document_links()

        #: Then
        assert links == (
            DocumentLink(
                line=LineNumber(NonZeroUnsignedInt(3)),
                url='../feat/a.md',
                corpus='feat',
                filename='a',
                has_back_link=True,
            ),
            DocumentLink(
                line=LineNumber(NonZeroUnsignedInt(4)), url='b.md', corpus='code', filename='b', has_back_link=False
            ),
        ), 'existing documents only, README and the missing file left out, each with its url and back link'

    def test_document_links_called_twice_returns_the_first_answer(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(self._snapshot(tmp_path))
        source = _decoded(database)
        first = database.item_document_links(source)

        #: When
        second = database.item_document_links(source)

        #: Then
        assert second is first, 'the links are memoized'

    def test_document_links_of_a_skill_entry_raises_wrong_item_kind_error(self, tmp_path: Path) -> None:
        #: Given
        context = _context(Database.from_snapshot(_snapshot(tmp_path)), SKILL)

        #: When / Then
        with pytest.raises(WrongItemKindError):
            context.document_links()
