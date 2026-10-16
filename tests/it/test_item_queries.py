"""The unified query family of the database, keyed by the common reference of a document or a skill entry.

A document and a skill entry decode to one witness type and are asked the same per-file, governance and link-target
questions; each answer is computed on demand and kept for the database's lifetime. Every snapshot is built in memory.
"""

from pathlib import Path
from typing import Final

import pytest

from lib.tree import from_tree
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.database import Database, ItemText, Undecodable
from lorecraft.project.document import DocumentRef
from lorecraft.project.item import MarkdownItemRef, UnlistedItemError
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.vfs import Snapshot, take_snapshot

GUIDE: Final[MarkdownItemRef] = MarkdownItemRef(RootRelativePath.parse('docs/code/guide.md'))
REVIEW: Final[MarkdownItemRef] = MarkdownItemRef(RootRelativePath.parse('.agents/skills/review/SKILL.md'))
GUIDE_TEXT: Final[bytes] = b'---\nname: guide\n---\n# Guide\n'
SKILL_TEXT: Final[bytes] = b'---\nname: review\n---\n'


def _snapshot(guide: bytes = GUIDE_TEXT, skill: bytes = SKILL_TEXT) -> Snapshot:
    """A snapshot with a `code` corpus holding `guide.md` and the skill `.agents/skills/review/`."""
    return from_tree(
        {
            'docs': {
                '__meta__': {'code.md': b'# Code\n', 'code.spec.json': b'{"frontmatter": {"type": "object"}}'},
                'code': {'guide.md': guide},
            },
            '.agents': {'skills': {'review': {'SKILL.md': skill}}},
        }
    )


def _decoded(database: Database, ref: MarkdownItemRef) -> ItemText:
    """The witness of an item the test wrote as UTF-8."""
    source = database.item_text(ref)
    assert isinstance(source, ItemText), f'{ref.path} was written as UTF-8, so it decodes'
    return source


@pytest.mark.it
class TestItemQueries:
    def test_item_text_of_a_document_and_a_skill_entry_returns_one_witness_type(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())

        #: When
        document = database.item_text(GUIDE)
        skill = database.item_text(REVIEW)

        #: Then
        assert isinstance(document, ItemText), 'a document decodes to the shared witness'
        assert isinstance(skill, ItemText), 'a skill entry decodes to the same witness type'
        assert (document.ref, skill.ref) == (GUIDE, REVIEW), 'each witness is keyed by its common ref'

    def test_item_text_of_a_file_that_is_not_utf8_returns_one_marker_without_per_file_facts(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(skill=b'---\nname: caf\xe9\n---\n'))

        #: When
        first = database.item_text(REVIEW)

        #: Then
        assert isinstance(first, Undecodable), 'the file is not UTF-8'
        assert first.ref == REVIEW, 'the marker names the common ref'
        assert database.item_text(REVIEW) is first, 'an undecodable file is decoded once'

    def test_item_queries_called_twice_return_the_first_answer(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        source = _decoded(database, GUIDE)

        #: Then
        assert database.item_text(GUIDE) is source, 'the decode is memoized by the common ref'
        assert database.item_parse(source) is database.item_parse(source), 'the parse is memoized'
        assert database.item_frontmatter(source) is database.item_frontmatter(source), 'the frontmatter is memoized'
        assert database.item_line_count(source) is database.item_line_count(source), 'the line count is memoized'
        assert database.item_token_count(source) is database.item_token_count(source), 'the token count is memoized'

    def test_item_text_after_the_linked_entry_is_retargeted_reads_the_newly_recorded_file(self, tmp_path: Path) -> None:
        #: Given
        for target in ('a', 'b'):
            (tmp_path / target).mkdir()
            (tmp_path / target / 'SKILL.md').write_bytes(f'---\nname: {target}\n---\n'.encode())
        skills = tmp_path / '.agents' / 'skills'
        skills.mkdir(parents=True)
        (skills / 'review').symlink_to('../../a')
        before = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE))
        (skills / 'review').unlink()
        (skills / 'review').symlink_to('../../b')
        after = Database.from_snapshot(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        old = _decoded(before, REVIEW)
        new = _decoded(after, REVIEW)

        #: Then
        assert old.ref == new.ref == REVIEW, 'the ref is unchanged'
        assert (old.text, new.text) == ('---\nname: a\n---\n', '---\nname: b\n---\n'), 'the text follows the link'

    def test_item_after_a_compatibility_entry_point_resolved_an_unlisted_document_still_refuses_it(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        unlisted = DocumentRef(CorpusName.parse('other'), AspectFilename.parse('x'))
        database.governance(unlisted)

        #: Then
        with pytest.raises(UnlistedItemError):
            database.item(MarkdownItemRef(unlisted.path))

    def test_item_with_a_ref_the_model_does_not_list_raises_unlisted_item_error(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())

        #: Then
        with pytest.raises(UnlistedItemError):
            database.item_text(MarkdownItemRef(RootRelativePath.parse('docs/code/missing.md')))
