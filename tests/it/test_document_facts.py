"""The document-fact queries of the database and the context methods over them, for one governed document.

Each query is computed once per database; the context hands the same value back, and answers nothing for a skill entry.
"""

from pathlib import Path
from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import Database, DatabaseItemContext, ItemText
from lorecraft.project.database.context import WrongItemKindError
from lorecraft.project.item import MarkdownItemRef
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.vfs import Snapshot, take_snapshot

GUIDE: Final[MarkdownItemRef] = MarkdownItemRef(RootRelativePath.parse('docs/code/guide.md'))
SKILL: Final[MarkdownItemRef] = MarkdownItemRef(RootRelativePath.parse('.agents/skills/review/SKILL.md'))
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


@pytest.mark.it
class TestDocumentFactQueries:
    def test_queries_called_twice_return_the_first_answer(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))
        source = database.item_text(GUIDE)
        assert isinstance(source, ItemText), 'the guide decodes'

        #: Then
        assert database.item_title(source) is database.item_title(source), 'the title is memoized'
        assert database.item_title_constraints(GUIDE) is database.item_title_constraints(GUIDE), 'checks are memoized'
        assert database.item_token_budgets(GUIDE) is database.item_token_budgets(GUIDE), 'budgets are memoized'
        assert database.item_empty_section_specs(GUIDE) is database.item_empty_section_specs(GUIDE), (
            'specs are memoized'
        )
        assert database.item_empty_headings(source) is database.item_empty_headings(source), 'headings are memoized'
        assert database.item_extension_links(source) is database.item_extension_links(source), 'links are memoized'

    def test_context_hands_out_the_facts_of_the_document(self, tmp_path: Path) -> None:
        #: Given
        context = _context(Database.from_snapshot(_snapshot(tmp_path)), GUIDE)
        spec = RootRelativePath.parse('docs/__meta__/code.spec.json')

        #: Then
        title = context.title()
        assert title is not None, 'the document has a title'
        assert (title.chars.value, title.words.value) == (12, 3), 'the title is measured'
        assert [c.spec for c in context.title_constraints()] == [spec], 'the title checks name their file'
        assert [(b.spec, b.tokens.value) for b in context.token_budgets()] == [(spec, 500)], 'the budget names its file'
        assert context.empty_section_specs() == (spec,), 'the file that forbids empty sections'
        assert [h.text for h in context.empty_headings()] == ['Empty'], 'the one empty section'
        assert [(link.line.value, link.extension) for link in context.extension_links()] == [(7, 'guide-more.md')], (
            'only the link to an existing extension'
        )

    def test_context_of_a_skill_entry_raises_wrong_item_kind_error(self, tmp_path: Path) -> None:
        #: Given
        context = _context(Database.from_snapshot(_snapshot(tmp_path)), SKILL)

        #: Then
        with pytest.raises(WrongItemKindError):
            context.title()
