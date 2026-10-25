"""Typed read keys for symlink and reserved-corpus directory queries."""

from dataclasses import replace
from pathlib import Path

import pytest

import lorecraft.project.database.database as database_module
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import CorpusName, ReservedCorpusDirectoryRef
from lorecraft.project.database import Database, PrimitiveRead, Read
from lorecraft.project.item import ItemRef
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.query import (
    CorpusDirectoryPrimitives,
    ItemPrimitives,
    SchemaPrimitives,
    SymlinkPrimitives,
    item_base,
    item_parse,
)
from lorecraft.project.skill import OutsideSymlinkRef
from lorecraft.project.syntax import Heading
from lorecraft.project.workspace.builtin import AGENT_SKILLS_SPEC_LAYER as SKILLS_LAYER
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


def _reads_layout_subjects(primitives: ItemPrimitives) -> tuple[RootExit, CorpusName]:
    """Read both layout subject kinds from an item query."""
    symlink = OutsideSymlinkRef(RootRelativePath.parse('.agents/skills/outside'))
    directory = ReservedCorpusDirectoryRef(RootRelativePath.parse('docs/skills'))
    return primitives.query_at(symlink, _symlink_exit), primitives.query_at(directory, _reserved_corpus)


def _symlink_reads_item(primitives: SymlinkPrimitives) -> tuple[Heading, ...]:
    """Read an item query from a symlink query."""
    return primitives.query_at(ItemRef(RootRelativePath.parse('docs/code/source.md')), _item_headings)


def _corpus_directory_reads_item(primitives: CorpusDirectoryPrimitives) -> tuple[Heading, ...]:
    """Read an item query from a corpus-directory query."""
    return primitives.query_at(ItemRef(RootRelativePath.parse('docs/code/source.md')), _item_headings)


def _descriptor_origin(primitives: ItemPrimitives) -> object:
    """The origin held by the model."""
    return primitives.descriptor().origin


def _descriptor_listed_name(primitives: ItemPrimitives) -> str:
    """The listed name held by the model."""
    return primitives.descriptor().listed_name


def _governance(primitives: ItemPrimitives) -> object:
    """The governance held by the model."""
    return primitives.governance()


def _text(primitives: ItemPrimitives) -> object:
    """The decoded text input."""
    return primitives.text()


def _descriptor(primitives: ItemPrimitives) -> object:
    """The item's model-resolved descriptor."""
    return primitives.descriptor()


def _name_hierarchy(primitives: ItemPrimitives) -> object:
    """The name ancestor specific to this item."""
    return primitives.name_hierarchy()


def _link_base(primitives: ItemPrimitives) -> object:
    """The base path for links in the item's decoded text."""
    return primitives.link_base()


def _link_targets(primitives: ItemPrimitives) -> object:
    """The paths reached from links in the item's decoded text."""
    return primitives.link_targets()


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
        'docs/__meta__/code-python.md': b'# Python\n',
        'docs/__meta__/code.spec.json': b'{"tokens": 500}',
        'docs/code/source.md': b'# Source\n',
        'docs/code/guide.md': b'# Guide\n',
        'docs/code/guide-more.md': b'# More\n',
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
    return Database.from_snapshot(take_snapshot(root, SNAPSHOT_SCOPE), builtin_layers=(SKILLS_LAYER,))


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
            for name in _primitive_methods(adapter, excluded={'query', 'query_at', 'query_schema'}):
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
        assert database.query_reads(_item_headings, ref) == {
            Read(item_parse, ref),
            Read(PrimitiveRead.TEXT, ref),
        }, 'the read key retains the Markdown item subject'

    def test_descriptor_origin_reads_the_descriptor_primitive(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        ref = ItemRef(RootRelativePath.parse('docs/code/source.md'))

        #: When
        database.query(_descriptor_origin, ref)

        #: Then
        assert database.query_reads(_descriptor_origin, ref) == {Read(PrimitiveRead.DESCRIPTOR, ref)}, (
            'the origin is read through the descriptor primitive'
        )

    def test_descriptor_listed_name_reads_the_descriptor_primitive(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        ref = ItemRef(RootRelativePath.parse('docs/code/source.md'))

        #: When
        database.query(_descriptor_listed_name, ref)

        #: Then
        assert database.query_reads(_descriptor_listed_name, ref) == {Read(PrimitiveRead.DESCRIPTOR, ref)}

    def test_governance_primitive_records_only_its_own_input(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        ref = ItemRef(RootRelativePath.parse('docs/code/source.md'))

        #: When
        database.query(_governance, ref)

        #: Then
        assert database.query_reads(_governance, ref) == {Read(PrimitiveRead.GOVERNANCE, ref)}

    def test_text_primitive_records_only_its_own_input(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        ref = ItemRef(RootRelativePath.parse('docs/code/source.md'))

        #: When
        database.query(_text, ref)

        #: Then
        assert database.query_reads(_text, ref) == {Read(PrimitiveRead.TEXT, ref)}

    def test_descriptor_primitive_records_only_its_own_input(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        ref = ItemRef(RootRelativePath.parse('docs/code/source.md'))

        #: When
        database.query(_descriptor, ref)

        #: Then
        assert database.query_reads(_descriptor, ref) == {Read(PrimitiveRead.DESCRIPTOR, ref)}

    def test_name_hierarchy_primitive_records_only_its_own_input(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        ref = ItemRef(RootRelativePath.parse('docs/code/source.md'))

        #: When
        database.query(_name_hierarchy, ref)

        #: Then
        assert database.query_reads(_name_hierarchy, ref) == {
            Read(PrimitiveRead.NAME_HIERARCHY, ref),
            Read(PrimitiveRead.DESCRIPTOR, ref),
        }

    def test_name_hierarchy_is_unchanged_by_an_unrelated_schema_change(self, tmp_path: Path) -> None:
        #: Given
        original = _database(tmp_path / 'original')
        changed = _database(tmp_path / 'changed')
        ref = ItemRef(RootRelativePath.parse('docs/code/guide-more.md'))
        original_model = original.model()
        changed._model = replace(changed.model(), schema_inputs=FrozenMapping({}))
        assert original_model.schema_inputs != changed.model().schema_inputs, 'the model has unrelated schema changes'

        #: When
        original_hierarchy = original.query(_name_hierarchy, ref)
        changed_hierarchy = changed.query(_name_hierarchy, ref)

        #: Then
        assert changed_hierarchy == original_hierarchy, "a schema change does not alter the item's name hierarchy"

    def test_link_base_primitive_records_its_decoded_inputs(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        ref = ItemRef(RootRelativePath.parse('docs/code/source.md'))

        #: When
        database.query(_link_base, ref)

        #: Then
        assert database.query_reads(_link_base, ref) == {
            Read(PrimitiveRead.LINK_BASE, ref),
            Read(PrimitiveRead.TEXT, ref),
            Read(PrimitiveRead.DESCRIPTOR, ref),
        }

    def test_item_base_records_document_hierarchy_inputs(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        ref = ItemRef(RootRelativePath.parse('docs/code/guide-more.md'))

        #: When
        database.query(item_base, ref)

        #: Then
        assert database.query_reads(item_base, ref) == {
            Read(PrimitiveRead.TEXT, ref),
            Read(PrimitiveRead.DESCRIPTOR, ref),
            Read(PrimitiveRead.NAME_HIERARCHY, ref),
        }

    def test_item_base_records_spec_hierarchy_inputs(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        ref = ItemRef(RootRelativePath.parse('docs/__meta__/code-python.md'))

        #: When
        database.query(item_base, ref)

        #: Then
        assert database.query_reads(item_base, ref) == {
            Read(PrimitiveRead.TEXT, ref),
            Read(PrimitiveRead.DESCRIPTOR, ref),
            Read(PrimitiveRead.NAME_HIERARCHY, ref),
        }

    def test_query_records_text_as_link_targets_dependency(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        ref = ItemRef(RootRelativePath.parse('docs/code/source.md'))

        #: When
        database.query(_link_targets, ref)

        #: Then
        assert database.query_reads(_link_targets, ref) == {
            Read(PrimitiveRead.LINK_TARGETS, ref),
            Read(PrimitiveRead.TEXT, ref),
        }, 'link targets read the item text through its own primitive'

    def test_query_records_a_schema_subject_primitive(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        ref: SchemaRef = AGENT_SKILLS_SCHEMA_REFERENCE
        expected = database.model().schema_inputs[ref]

        #: When
        schema = database.query(_schema_input, ref)

        #: Then
        assert schema == expected, 'the query returns the schema input identified by its subject'
        assert database.query_reads(_schema_input, ref) == {Read(PrimitiveRead.SCHEMA_INPUT, ref)}, (
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
        assert database.query_reads(_symlink_exit, ref) == {Read(PrimitiveRead.LEAVES_AT, ref)}, (
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
        assert database.query_reads(_reserved_corpus, ref) == {Read(PrimitiveRead.RESERVED_CORPUS, ref)}, (
            'the read set identifies the reserved-corpus primitive'
        )

    def test_query_at_composes_every_target_kind_from_items(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        item = ItemRef(RootRelativePath.parse('docs/code/source.md'))
        symlink = database.model().sorted_outside_symlinks[0]
        directory = database.model().sorted_overlapping_directories[0]

        #: When
        exits, corpora = database.query(_reads_layout_subjects, item)

        #: Then
        assert exits == symlink.leaves_at, 'query_at reads the typed symlink subject'
        assert corpora == directory.corpus, 'query_at reads the typed corpus-directory subject'
        assert database.query_reads(_reads_layout_subjects, item) == {
            Read(_symlink_exit, OutsideSymlinkRef(symlink.path)),
            Read(PrimitiveRead.LEAVES_AT, OutsideSymlinkRef(symlink.path)),
            Read(_reserved_corpus, ReservedCorpusDirectoryRef(directory.path)),
            Read(PrimitiveRead.RESERVED_CORPUS, ReservedCorpusDirectoryRef(directory.path)),
        }, 'each nested read keeps its target subject'

    def test_query_at_composes_item_queries_from_layout_subjects(self, tmp_path: Path) -> None:
        #: Given
        database = _database(tmp_path)
        item = ItemRef(RootRelativePath.parse('docs/code/source.md'))
        symlink = OutsideSymlinkRef(database.model().sorted_outside_symlinks[0].path)
        directory = ReservedCorpusDirectoryRef(database.model().sorted_overlapping_directories[0].path)

        #: When
        from_symlink = database.query(_symlink_reads_item, symlink)
        from_directory = database.query(_corpus_directory_reads_item, directory)

        #: Then
        assert tuple(heading.text for heading in from_symlink) == ('Source',), 'the symlink query reads the item'
        assert tuple(heading.text for heading in from_directory) == ('Source',), (
            'the corpus-directory query reads the item'
        )
        expected = {Read(_item_headings, item), Read(item_parse, item), Read(PrimitiveRead.TEXT, item)}
        assert database.query_reads(_symlink_reads_item, symlink) == expected, 'symlink reads retain item dependencies'
        assert database.query_reads(_corpus_directory_reads_item, directory) == expected, (
            'corpus-directory reads retain item dependencies'
        )
