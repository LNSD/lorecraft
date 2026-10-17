"""The document-fact queries of the database and the context methods over them, for one governed document.

Each query is computed once per database, a fresh one included; the context refuses a skill entry.
"""

from pathlib import Path
from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import Database, DatabaseItemContext, ItemText
from lorecraft.project.database.context import WrongItemKindError
from lorecraft.project.item import MarkdownItemRef, UnlistedItemError
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.vfs import Snapshot, take_snapshot

GUIDE: Final[MarkdownItemRef] = MarkdownItemRef(RootRelativePath.parse('docs/code/guide.md'))
SKILL: Final[MarkdownItemRef] = MarkdownItemRef(RootRelativePath.parse('.agents/skills/review/SKILL.md'))
SPEC_PATH: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.spec.json')
SPEC: Final[bytes] = b'{"tokens": 500, "title": {"words": 2}}'
TEXT: Final[bytes] = b'# A Long Title\n\n## Full\n\nText.\n'


def _snapshot(root: Path) -> Snapshot:
    """A scanned `code` corpus with a `guide` document, and a skill.

    Args:
        root: The empty directory the repository is written to.
    """
    files = {
        'docs/__meta__/code.md': b'# Code\n',
        'docs/__meta__/code.spec.json': SPEC,
        'docs/code/guide.md': TEXT,
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

    def test_item_title_constraints_called_twice_returns_the_first_answer(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))
        first = database.item_title_constraints(GUIDE)

        #: When
        second = database.item_title_constraints(GUIDE)

        #: Then
        assert second is first, 'the checks are memoized'

    def test_item_token_budgets_called_twice_returns_the_first_answer(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))
        first = database.item_token_budgets(GUIDE)

        #: When
        second = database.item_token_budgets(GUIDE)

        #: Then
        assert second is first, 'the budgets are memoized'

    def test_item_title_constraints_on_a_fresh_database_holds_the_checks_of_the_governing_specification(
        self, tmp_path: Path
    ) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))

        #: When
        constraints = database.item_title_constraints(GUIDE)

        #: Then
        assert [c.spec for c in constraints] == [SPEC_PATH], 'the item is resolved by the query itself'

    def test_item_token_budgets_on_a_fresh_database_holds_the_budget_of_the_governing_specification(
        self, tmp_path: Path
    ) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))

        #: When
        budgets = database.item_token_budgets(GUIDE)

        #: Then
        assert [(b.spec, b.tokens.value) for b in budgets] == [(SPEC_PATH, 500)], 'the item is resolved by the query'

    def test_item_title_constraints_of_an_unlisted_path_raises_unlisted_item_error(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))

        #: When / Then
        with pytest.raises(UnlistedItemError):
            database.item_title_constraints(MarkdownItemRef(RootRelativePath.parse('README.md')))

    def test_item_token_budgets_of_an_unlisted_path_raises_unlisted_item_error(self, tmp_path: Path) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(tmp_path))

        #: When / Then
        with pytest.raises(UnlistedItemError):
            database.item_token_budgets(MarkdownItemRef(RootRelativePath.parse('README.md')))


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

    def test_title_constraints_names_the_file_that_states_them(self, tmp_path: Path) -> None:
        #: Given
        context = _context(Database.from_snapshot(_snapshot(tmp_path)), GUIDE)

        #: When
        constraints = context.title_constraints()

        #: Then
        assert [c.spec for c in constraints] == [SPEC_PATH], 'the title checks name their file'

    def test_token_budgets_names_the_file_that_sets_them(self, tmp_path: Path) -> None:
        #: Given
        context = _context(Database.from_snapshot(_snapshot(tmp_path)), GUIDE)

        #: When
        budgets = context.token_budgets()

        #: Then
        assert [(b.spec, b.tokens.value) for b in budgets] == [(SPEC_PATH, 500)], 'the budget names its file'

    def test_title_of_a_skill_entry_raises_wrong_item_kind_error(self, tmp_path: Path) -> None:
        #: Given
        context = _context(Database.from_snapshot(_snapshot(tmp_path)), SKILL)

        #: When / Then
        with pytest.raises(WrongItemKindError):
            context.title()

    def test_title_constraints_of_a_skill_entry_raises_wrong_item_kind_error(self, tmp_path: Path) -> None:
        #: Given
        context = _context(Database.from_snapshot(_snapshot(tmp_path)), SKILL)

        #: When / Then
        with pytest.raises(WrongItemKindError):
            context.title_constraints()

    def test_token_budgets_of_a_skill_entry_raises_wrong_item_kind_error(self, tmp_path: Path) -> None:
        #: Given
        context = _context(Database.from_snapshot(_snapshot(tmp_path)), SKILL)

        #: When / Then
        with pytest.raises(WrongItemKindError):
            context.token_budgets()
