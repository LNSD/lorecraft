"""The database answers the common `item_*` queries for a skill's Markdown resources.

A resource keeps its own reference and location and takes the containing skill's governance identity; its links are
read from the skill root, and the model activates no facet but Markdown for it.
"""

from collections.abc import Mapping
from pathlib import PurePosixPath

import pytest

from lib.tree import from_tree
from lorecraft.core.path import RootRelativePath
from lorecraft.project.database import Database, ItemText
from lorecraft.project.item import ItemFacet, ItemKind, MarkdownItemRef, SkillResourceOrigin, UnlistedItemError
from lorecraft.project.skill import SkillResourceLocation
from lorecraft.vfs import (
    DirectoryRecord,
    EntryRecord,
    FileRecord,
    ResolvedPath,
    Snapshot,
    SnapshotRecords,
    SymlinkRecord,
)


def _resources(database: Database, skill: str) -> tuple[SkillResourceLocation, ...]:
    """The resources the database lists for the skill in `.agents/skills/<skill>`."""
    location = database.model().find_skill_location(RootRelativePath.parse(f'.agents/skills/{skill}'))
    assert location is not None, f'the model lists the skill {skill}'
    return database.skill_resources(location).resources


def _text(database: Database, location: SkillResourceLocation) -> ItemText:
    """The witness of a resource the test wrote as UTF-8, read through the common queries."""
    source = database.item_text(database.resource_item(location))
    assert isinstance(source, ItemText), f'{location.ref.path} was written as UTF-8, so it decodes'
    return source


def _snapshot_of(records: Mapping[str, EntryRecord]) -> Snapshot:
    """A snapshot holding `records`, each keyed by its root-relative path."""
    return Snapshot(SnapshotRecords({RootRelativePath.parse(raw): record for raw, record in records.items()}), scope=())


@pytest.mark.it
class TestResourceItems:
    def test_item_text_of_a_resource_returns_its_text_with_the_resource_descriptor(self) -> None:
        #: Given
        snapshot = from_tree(
            {'.agents': {'skills': {'review': {'SKILL.md': b'# Review\n', 'guides': {'a.md': b'[b](guides/b.md)\n'}}}}}
        )
        database = Database.from_snapshot(snapshot)
        (location,) = _resources(database, 'review')

        #: When
        source = _text(database, location)

        #: Then
        descriptor = source.descriptor
        assert source.text == '[b](guides/b.md)\n', 'the text is the resource file decoded'
        assert descriptor.ref == MarkdownItemRef(location.ref.path), 'the resource keeps its own reported path'
        assert descriptor.kind is ItemKind.SKILL_RESOURCE, 'the descriptor is for a skill resource'
        assert descriptor.read_location == location.resolves_to, 'the text is read at the listed resolved file'
        assert descriptor.active_facets == {ItemFacet.MARKDOWN}, 'no entry-only facet is active for a resource'

    def test_item_text_of_resources_with_the_same_filename_keeps_a_ref_and_owner_for_each(self) -> None:
        #: Given
        snapshot = from_tree(
            {
                '.agents': {
                    'skills': {
                        'review': {'SKILL.md': b'# R\n', 'guide.md': b'one\n'},
                        'deploy': {'SKILL.md': b'# D\n', 'guide.md': b'two\n'},
                    }
                }
            }
        )
        database = Database.from_snapshot(snapshot)

        #: When
        sources = [_text(database, _resources(database, skill)[0]) for skill in ('review', 'deploy')]

        #: Then
        assert sources[0].ref != sources[1].ref, 'identical filenames in different skills are different items'
        owners = [source.descriptor.origin for source in sources]
        assert owners == [SkillResourceOrigin('review'), SkillResourceOrigin('deploy')], (
            f'each resource inherits its own skill as owner, got {owners}'
        )
        assert [source.descriptor.aspect_name for source in sources] == ['review', 'deploy'], (
            'governance is matched by the skill name, never by the resource filename'
        )

    def test_item_text_of_a_retargeted_resource_symlink_keeps_the_ref_and_moves_the_location(self) -> None:
        #: Given
        def database_of(target: str) -> Database:
            return Database.from_snapshot(
                _snapshot_of(
                    {
                        '.': DirectoryRecord(listed=True),
                        '.agents': DirectoryRecord(listed=True),
                        '.agents/skills': DirectoryRecord(listed=True),
                        '.agents/skills/review': DirectoryRecord(listed=True),
                        '.agents/skills/review/SKILL.md': FileRecord(b'# R\n'),
                        '.agents/skills/review/guide.md': SymlinkRecord(PurePosixPath(f'../../../shared/{target}.md')),
                        'shared': DirectoryRecord(listed=True),
                        'shared/a.md': FileRecord(b'a\n'),
                        'shared/b.md': FileRecord(b'b\n'),
                    }
                )
            )

        #: When
        sources = []
        for target in ('a', 'b'):
            database = database_of(target)
            sources.append(_text(database, _resources(database, 'review')[0]))

        #: Then
        assert sources[0].ref == sources[1].ref, 'retargeting the link leaves the identity'
        assert [source.descriptor.read_location for source in sources] == [
            ResolvedPath(RootRelativePath.parse('shared/a.md')),
            ResolvedPath(RootRelativePath.parse('shared/b.md')),
        ], 'only the location follows the link'
        assert [source.text for source in sources] == ['a\n', 'b\n'], 'the text is read at the new location'

    def test_item_link_targets_of_a_resource_reads_links_from_the_skill_root(self) -> None:
        #: Given
        snapshot = from_tree(
            {
                '.agents': {
                    'skills': {
                        'review': {
                            'SKILL.md': b'# R\n',
                            'guides': {'a.md': b'[b](guides/b.md) [gone](guides/gone.md)\n', 'b.md': b'b\n'},
                        }
                    }
                }
            }
        )
        database = Database.from_snapshot(snapshot)
        location = _resources(database, 'review')[0]

        #: When
        targets = database.item_link_targets(_text(database, location))

        #: Then
        by_path = {str(path): entry for path, entry in targets.items()}
        assert set(by_path) == {'guides/b.md', 'guides/gone.md'}, (
            f'links are spelled from the skill root, got {by_path}'
        )
        assert by_path['guides/b.md'] != by_path['guides/gone.md'], 'a present and a missing target are told apart'

    def test_item_with_a_resource_ref_still_refuses_it_as_unlisted(self) -> None:
        #: Given
        database = Database.from_snapshot(
            from_tree({'.agents': {'skills': {'review': {'SKILL.md': b'# R\n', 'a.md': b'a\n'}}}})
        )
        location = _resources(database, 'review')[0]
        ref = database.resource_item(location)

        #: When / Then
        with pytest.raises(UnlistedItemError):
            database.item(ref)

    def test_item_text_of_an_unregistered_resource_path_raises_unlisted(self) -> None:
        #: Given
        database = Database.from_snapshot(
            from_tree({'.agents': {'skills': {'review': {'SKILL.md': b'# R\n', 'a.md': b'a\n'}}}})
        )

        #: When / Then
        with pytest.raises(UnlistedItemError):
            database.item_text(MarkdownItemRef(RootRelativePath.parse('.agents/skills/review/a.md')))

    def test_listing_a_skill_stays_lazy_until_a_resource_is_asked_for(self) -> None:
        #: Given
        database = Database.from_snapshot(
            from_tree({'.agents': {'skills': {'review': {'SKILL.md': b'# R\n', 'a.md': b'a\n'}}}})
        )

        #: When
        database.item_text(MarkdownItemRef(RootRelativePath.parse('.agents/skills/review/SKILL.md')))

        #: Then
        assert not database._skill_resources, 'deciding a skill entry lists no resources'  # noqa: SLF001
