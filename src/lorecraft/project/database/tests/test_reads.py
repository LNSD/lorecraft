"""Typed read keys for symlink and reserved-corpus directory queries."""

from pathlib import Path

import pytest

import lorecraft.project.database.database as database_module
from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import CorpusName, ReservedCorpusDirectoryRef
from lorecraft.project.database import Database, Read
from lorecraft.project.item import ItemRef
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.query import (
    CorpusDirectoryPrimitives,
    ItemPrimitives,
    SchemaPrimitives,
    SymlinkPrimitives,
    item_parse,
)
from lorecraft.project.skill import OutsideSymlinkRef
from lorecraft.project.syntax import Heading
from lorecraft.schemas import SchemaInput, SchemaRef
from lorecraft.schemas.builtin import AGENT_SKILLS_SCHEMA_REFERENCE
from lorecraft.vfs import RootExit, take_snapshot


def _symlink_exit(primitives: SymlinkPrimitives) -> RootExit:
    """The exit point recorded for a symlink subject."""
    return primitives.leaves_at()


def _reserved_corpus(primitives: CorpusDirectoryPrimitives) -> CorpusName:
    """The reserved name recorded for a corpus directory subject."""
    return primitives.reserved_corpus()


def _item_headings(primitives: ItemPrimitives) -> tuple[Heading, ...]:
    """The headings read from a Markdown item subject."""
    return primitives.query(item_parse).headings


def _read_only_lookup(primitives: ItemPrimitives) -> object:
    """Fetch a primitive method without invoking it."""
    return primitives.text


def _schema_input(primitives: SchemaPrimitives) -> SchemaInput:
    """The immutable input read from a schema subject."""
    return primitives.schema_input()


def _database(root: Path) -> Database:
    """Build a real database containing layout subjects of both kinds."""
    files = {
        'docs/__meta__/code.md': b'# Code\n',
        'docs/__meta__/skills.md': b'# Skills\n',
        'docs/code/source.md': b'# Source\n',
        'docs/feat/target.md': b'# Target\n',
    }
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (root / 'docs' / 'skills').mkdir()
    outside = root.parent / f'{root.name}-outside'
    outside.mkdir()
    skill_links = root / '.agents' / 'skills'
    skill_links.mkdir(parents=True)
    (skill_links / 'outside').symlink_to(outside, target_is_directory=True)
    return Database.from_snapshot(take_snapshot(root, SNAPSHOT_SCOPE))


def _primitive_methods(adapter: type[object], *, excluded: set[str]) -> frozenset[str]:
    """The public primitive methods declared directly on a recording adapter."""
    return frozenset(name for name in vars(adapter) if not name.startswith('_') and name not in excluded)


@pytest.mark.unit
class TestSubjectReads:
    def test_every_database_primitive_is_decorated(self) -> None:
        #: Given
        adapters = (
            '_ItemPrimitives',
            '_SymlinkPrimitives',
            '_CorpusDirectoryPrimitives',
            '_SchemaPrimitives',
        )

        #: Then
        for adapter_name in adapters:
            adapter = getattr(database_module, adapter_name)
            for name in _primitive_methods(adapter, excluded={'schema_input', 'query', 'query_at', 'query_schema'}):
                assert getattr(adapter, name).__wrapped__.__name__ == name, (
                    f'{adapter_name}.{name} records its read before calling the primitive'
                )

    def test_fetching_a_primitive_method_without_calling_it_records_nothing(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        ref = ItemRef(RootRelativePath.parse('docs/code/source.md'))

        #: When
        database.query(_read_only_lookup, ref)

        #: Then
        assert database.query_reads(_read_only_lookup, ref) == frozenset(), (
            'looking up a primitive method does not read it'
        )

    def test_query_records_a_markdown_item_subject_primitive(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        ref = ItemRef(RootRelativePath.parse('docs/code/source.md'))

        #: When
        headings = database.query(_item_headings, ref)

        #: Then
        assert len(headings) == 1, f'the query returns the source heading, got {headings}'
        assert database.query_reads(_item_headings, ref) == {Read(item_parse, ref), Read('text', ref)}, (
            'the read key retains the Markdown item subject'
        )

    def test_query_records_a_schema_subject_primitive(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        ref: SchemaRef = AGENT_SKILLS_SCHEMA_REFERENCE
        expected = database.model().schema_inputs[ref]

        #: When
        schema = database.query(_schema_input, ref)

        #: Then
        assert schema == expected, 'the query returns the schema input identified by its subject'
        assert database.query_reads(_schema_input, ref) == {Read('schema_input', ref)}, (
            'the read key retains the typed schema subject'
        )

    def test_query_records_a_symlink_subject_primitive(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        symlink = database.model().sorted_outside_symlinks[0]
        ref = OutsideSymlinkRef(symlink.path)

        #: When
        exit_point = database.query(_symlink_exit, ref)

        #: Then
        assert exit_point == symlink.leaves_at, 'the query returns the symlink exit recorded by the model'
        assert database.query_reads(_symlink_exit, ref) == {Read('leaves_at', ref)}, (
            'the read set identifies the symlink primitive'
        )

    def test_query_records_a_reserved_corpus_directory_primitive(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        directory = database.model().sorted_overlapping_directories[0]
        ref = ReservedCorpusDirectoryRef(directory.path)

        #: When
        corpus = database.query(_reserved_corpus, ref)

        #: Then
        assert corpus == directory.corpus, 'the query returns the reserved corpus named by the model'
        assert database.query_reads(_reserved_corpus, ref) == {Read('reserved_corpus', ref)}, (
            'the read set identifies the reserved-corpus primitive'
        )
