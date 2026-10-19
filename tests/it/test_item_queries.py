"""The unified query family of the database, keyed by the common reference of a document or a skill.

A document and a skill decode to one witness type and are asked the same per-file, governance and link-target
questions; each answer is computed on demand and kept for the database's lifetime. Every snapshot is built in memory.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest

from lib.database import listed_item
from lib.tree import from_tree
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.database import Database, ItemText, Read, Undecodable
from lorecraft.project.document import DocumentRef
from lorecraft.project.item import ItemOrigin, ItemReadError, ItemRef, SkillEntrypointOrigin, UnlistedItemError
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.link_target import EscapingTarget, LinkTarget, PathLookup
from lorecraft.project.query import (
    ItemPrimitives,
    item_corpus,
    item_frontmatter,
    item_line_count,
    item_name,
    item_parse,
    item_token_count,
)
from lorecraft.project.schemas import SpecName, frontmatter_schema_problems, outline_alignment
from lorecraft.project.syntax import NormalisedLinkPath
from lorecraft.project.workspace import WorkspaceModel
from lorecraft.vfs import Snapshot, VirtualFileSystem, take_snapshot

GUIDE: Final[ItemRef] = ItemRef(RootRelativePath.parse('docs/code/guide.md'))
REVIEW: Final[ItemRef] = ItemRef(RootRelativePath.parse('.agents/skills/review/SKILL.md'))
LINKS: Final[bytes] = b'---\nname: x\n---\n[up](../up.md)\n[far](../../far.md)\n'

GUIDE_TEXT: Final[bytes] = b'---\nname: guide\n---\n# Guide\n'
SKILL_TEXT: Final[bytes] = b'---\nname: review\n---\n'


class TracingDatabase(Database):
    """A database that records which per-file queries are computed, then computes them as usual."""

    def __init__(self, fs: VirtualFileSystem, model: WorkspaceModel) -> None:
        """Build the database on the view, with nothing computed yet.

        Args:
            fs: The view of the revision the database reads.
            model: The workspace model loaded through the view.
        """
        super().__init__(fs, model)
        self.computed: list[str] = []

    def _memo_query[T](self, key: Read, answer: Callable[[], T], reads: Callable[[], frozenset[Read]]) -> T:
        """Record per-item query evaluations, then memoize them as usual."""
        if key.source is item_frontmatter:
            self.computed.append('frontmatter')
        elif key.source is item_parse:
            self.computed.append('parse')
        return super()._memo_query(key, answer, reads)


def _snapshot(guide: bytes = GUIDE_TEXT, skill: bytes = LINKS) -> Snapshot:
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


def _decoded(database: Database, ref: ItemRef) -> ItemText:
    """The witness of an item the test wrote as UTF-8."""
    source = database.item_text(ref)
    assert isinstance(source, ItemText), f'{ref.path} was written as UTF-8, so it decodes'
    return source


def _item_origin(primitives: ItemPrimitives) -> ItemOrigin:
    """The item's model-resolved origin, which does not require decoded text."""
    return primitives.origin()


def _item_name(primitives: ItemPrimitives) -> AspectFilename | SpecName | None:
    """The item's decoded name, when it has one."""
    return primitives.query(item_name)


def _item_corpus(primitives: ItemPrimitives) -> CorpusName | None:
    """The item's decoded corpus, when it is a document."""
    return primitives.query(item_corpus)


def _item_base(primitives: ItemPrimitives) -> AspectFilename | SpecName | None:
    """The item's decoded base name, when it has one."""
    return primitives.base()


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
        assert isinstance(skill, ItemText), 'a skill decodes to the same witness type'
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

    def test_item_primitives_answer_undecodable_text_consistently(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(skill=b'---\nname: caf\xe9\n---\n'))
        source = database.item_text(REVIEW)
        assert isinstance(source, Undecodable), 'the skill is not UTF-8'

        #: When
        origin = database.query(_item_origin, REVIEW)
        name = database.query(_item_name, REVIEW)
        corpus = database.query(_item_corpus, REVIEW)
        base = database.query(_item_base, REVIEW)

        #: Then
        assert isinstance(origin, SkillEntrypointOrigin), "the resolved item's origin survives invalid text"
        assert (name, corpus, base) == (None, None, None), 'content-derived facts are empty without decoded text'

    def test_item_queries_called_twice_return_the_first_answer(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        source = _decoded(database, GUIDE)

        #: Then
        assert database.item_text(GUIDE) is source, 'the decode is memoized by the common ref'
        assert database.query(item_parse, source.ref) is database.query(item_parse, source.ref), 'the parse is memoized'
        assert database.query(item_frontmatter, source.ref) is database.query(item_frontmatter, source.ref), (
            'the frontmatter is memoized'
        )
        assert database.query(item_line_count, source.ref) is database.query(item_line_count, source.ref), (
            'the line count is memoized'
        )
        assert database.query(item_token_count, source.ref) is database.query(item_token_count, source.ref), (
            'the token count is memoized'
        )

    def test_item_frontmatter_schema_problems_with_only_the_frontmatter_demanded_leaves_the_parse_uncomputed(
        self,
    ) -> None:
        #: Given
        database = TracingDatabase.from_snapshot(_snapshot())
        source = _decoded(database, GUIDE)

        #: When
        database.query(frontmatter_schema_problems, source.ref)
        database.query(frontmatter_schema_problems, source.ref)

        #: Then
        assert database.computed == ['frontmatter'], 'the frontmatter is computed once and no parse is demanded'

    def test_item_outline_alignment_of_an_ungoverned_skill_entry_reads_no_parse(self) -> None:
        #: Given
        database = TracingDatabase.from_snapshot(_snapshot())
        source = _decoded(database, REVIEW)

        #: When
        alignments = database.query(outline_alignment, source.ref)

        #: Then
        assert alignments == (), 'no specification governs it'
        assert database.computed == [], 'so nothing is parsed'

    def test_item_governance_returns_the_models_layers_for_a_document_and_none_for_a_skill_entry(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        document = database.model().find_document(GUIDE.path)
        assert document is not None, 'the model lists the document'

        #: Then
        assert database.item_governance(GUIDE) == database.model().find_governance(document), 'the model decides'
        assert database.item_governance(GUIDE) is database.item_governance(GUIDE), 'it is resolved once'
        assert database.item_governance(REVIEW) is None, 'no repository layer governs a skill yet'

    def test_item_link_targets_read_each_items_own_base_and_climb_bound(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(guide=LINKS))
        up = NormalisedLinkPath.parse('../up.md')
        far = NormalisedLinkPath.parse('../../far.md')

        #: When
        document = database.item_link_targets(_decoded(database, GUIDE))
        skill = database.item_link_targets(_decoded(database, REVIEW))

        #: Then
        assert document[up] == LinkTarget(RootRelativePath.parse('docs/up.md'), PathLookup.OUTSIDE_SCOPE), (
            'a document climbs from its own directory'
        )
        assert skill[up] == EscapingTarget(), 'a skill may not climb above its root'
        assert skill[far] == EscapingTarget(), 'however far'

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
        assert database.item_governance(ItemRef(unlisted.path)) is None, 'no corpus governs it'

        #: When
        with pytest.raises(UnlistedItemError) as raised:
            listed_item(database, ItemRef(unlisted.path))

        #: Then
        assert raised.value.ref == ItemRef(unlisted.path), 'the item stays refused'

    def test_item_governance_with_a_document_in_a_corpus_the_model_lacks_answers_none(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        unlisted = DocumentRef(CorpusName.parse('other'), AspectFilename.parse('x'))

        #: When
        governance = database.item_governance(ItemRef(unlisted.path))

        #: Then
        assert governance is None, 'no corpus governs it, and it is no error'

    def test_item_text_with_a_document_the_model_does_not_list_reads_it_from_its_path(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        unlisted = ItemRef(RootRelativePath.parse('docs/code/missing.md'))

        #: When
        with pytest.raises(ItemReadError) as raised:
            database.item_text(unlisted)

        #: Then
        assert raised.value.ref == unlisted, 'the file is read from its path, and a missing one is a read error'

    def test_item_text_with_a_path_naming_neither_a_document_nor_a_skill_raises_unlisted_item_error(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        elsewhere = ItemRef(RootRelativePath.parse('src/readme.md'))

        #: When
        with pytest.raises(UnlistedItemError) as raised:
            database.item_text(elsewhere)

        #: Then
        assert raised.value.ref == elsewhere, 'a path outside the corpora names no item'
