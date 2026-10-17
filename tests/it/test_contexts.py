"""The database-backed contexts, held to the protocols of `lorecraft.project` they implement.

Each method of `DocumentContext`, `SkillContext`, `SkillResourceContext` and `SymlinkContext` is asked through a
value typed as the protocol, over a database opened on an in-memory snapshot, or on a scan of a real tree where the
query needs a path in scope, and compared with what the database's matching query returns; a fact the database
memoizes is the very value the query keeps, so a context computes nothing of its own. The static hold of each class
to its protocol is in `lorecraft.project.database.tests.test_context`, where the type-checking gate reaches it.
"""

from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from textwrap import dedent
from typing import Final, assert_never

import pytest

from lib.tree import FileTree, from_tree
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.context import (
    CorpusDirectoryContext,
    DocumentContext,
    DocumentFrontmatterOwner,
    SkillContext,
    SkillFrontmatterOwner,
    SkillResourceContext,
    SymlinkContext,
)
from lorecraft.project.corpus import CorpusName, ReservedCorpusDirectory
from lorecraft.project.database import (
    Database,
    DatabaseCorpusDirectoryContext,
    DatabaseItemContext,
    DatabaseSymlinkContext,
    ItemText,
)
from lorecraft.project.database.context import WrongItemKindError
from lorecraft.project.document import DocumentRef, SpecRef
from lorecraft.project.item import MarkdownItemRef
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.link_target import DocumentDirectory, EscapingTarget, LinkTarget, PathLookup, SkillRoot
from lorecraft.project.skill import OutsideSymlink, SkillLocation, SkillRef
from lorecraft.project.syntax import NormalisedLinkPath, count_lines, count_tokens
from lorecraft.rules.length.too_many_lines import skill_line_count
from lorecraft.vfs import (
    EntryRecord,
    ResolvedPath,
    RootExit,
    Snapshot,
    SnapshotRecords,
    SymlinkRecord,
    take_snapshot,
)

TYPING: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-typing'))
"""A document of corpus `code` its `python` namespace governs too."""

TYPING_TEXT: Final[str] = (
    '---\nname: python-typing\nowner: 7\n---\n# Typing\n\n## Rule\n\nAnnotate every signature, as [the code corpus]'
    '(../__meta__/code.md) says, not [gone](gone.md), [the source](../../src/main.py) or [up](../../../x.md).\n'
)
"""The text of `TYPING`: a frontmatter whose `owner` the corpus schema rejects, a title and one section."""

CORPUS_STRUCTURE: Final[bytes] = (
    b'{"tokens": 400, "outline": [{"section": "Rule"}, {"section": "Checklist"}], '
    b'"frontmatter": {"type": "object", "properties": {"owner": {"type": "string"}}}}'
)
"""The corpus structure specification: a budget, an outline `TYPING` lacks a section of, and a frontmatter schema."""

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.spec.json')
"""Where the corpus structure specification lies."""

SPEC: Final[SpecRef] = SpecRef(RootRelativePath.parse('docs/__meta__/code-python.md'))
"""A meta specification, the namespace spec `python` of corpus `code`."""

SPEC_TEXT: Final[str] = dedent(
    """\
    # Code Python

    Read [the code spec](code.md), not [gone](gone.md).
    """
)
"""The text of `SPEC`: a title and two links, one to the corpus spec beside it and one to nothing."""

REVIEW: Final[SkillRef] = SkillRef(
    ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review')
)
"""A skill an agent reaches under `.agents/skills`."""

REVIEW_TEXT: Final[str] = (
    '---\nname: reviewer\n---\n# Review\n\nRead [the checklist](references/checklist.md), not '
    '[gone](references/gone.md) or [up](../x.md).\n'
)
"""The `SKILL.md` of `REVIEW`: a frontmatter missing the `description` the Agent Skills specification requires."""

CHECKLIST_TEXT: Final[str] = '# Checklist\n\nRead [the review](SKILL.md), not [gone](gone.md).\n'
"""The text of `REVIEW`'s one resource, `references/checklist.md`: a title and a link."""


def _tree() -> FileTree:
    """Corpus `code`, with a `python` namespace, holding `TYPING`, and `REVIEW` with one resource, as files."""
    return {
        '.agents': {
            'skills': {
                'review': {
                    'SKILL.md': REVIEW_TEXT.encode(),
                    'references': {'checklist.md': CHECKLIST_TEXT.encode()},
                }
            }
        },
        'docs': {
            '__meta__': {
                'code.md': b'# Code\n',
                'code.spec.json': CORPUS_STRUCTURE,
                'code-python.md': SPEC_TEXT.encode(),
                'code-python.spec.json': b'{"tokens": 200}',
            },
            'code': {'python-typing.md': TYPING_TEXT.encode()},
        },
    }


def _snapshot() -> Snapshot:
    """A snapshot of `_tree`, built in memory, so no path is in its scope."""
    return from_tree(_tree())


def _link_target(path: str, lookup: PathLookup) -> LinkTarget:
    """The target of a link: the root-relative path it leads to, and what the snapshot holds there.

    Args:
        path: The root-relative path the link leads to.
        lookup: What the snapshot holds at the path.
    """
    return LinkTarget(path=RootRelativePath.parse(path), lookup=lookup)


def _document_context(database: Database) -> DocumentContext:
    """The context of `TYPING`, typed as the protocol, so the type checker holds the class to it.

    Args:
        database: The database `TYPING` is read from.
    """
    return DatabaseItemContext(database, _document_item(database))


def _document_item(database: Database) -> ItemText:
    """The witness of `TYPING`, as the database decodes it by its common reference.

    Args:
        database: The database the document is decoded by.
    """
    source = database.item_text(MarkdownItemRef(TYPING.path))
    assert isinstance(source, ItemText), f'{TYPING.path} was written as UTF-8, so it decodes'
    return source


def _spec_item(database: Database) -> ItemText:
    """The witness of `SPEC`, as the database decodes it by its common reference.

    Args:
        database: The database the specification is decoded by.
    """
    source = database.item_text(MarkdownItemRef(SPEC.path))
    assert isinstance(source, ItemText), f'{SPEC.path} was written as UTF-8, so it decodes'
    return source


def _skill_item(database: Database) -> ItemText:
    """The witness of `REVIEW`'s `SKILL.md`, as the database decodes it by its common reference.

    Args:
        database: The database the `SKILL.md` is decoded by.
    """
    source = database.item_text(MarkdownItemRef(REVIEW.path))
    assert isinstance(source, ItemText), f'{REVIEW.path} was written as UTF-8, so it decodes'
    return source


def _location(database: Database) -> SkillLocation:
    """Where the database's model locates `REVIEW`.

    Args:
        database: The database whose model lists the skill.
    """
    location = database.model().find_skill_location(REVIEW.directory)
    assert location is not None, f'the model lists the skill {REVIEW.directory}'
    return location


def _resource_text(database: Database) -> ItemText:
    """The witness of `REVIEW`'s one resource, as the database decodes it at the file its listing locates.

    Args:
        database: The database the resource is listed and decoded by.
    """
    (resource,) = database.skill_resources(_location(database)).resources
    source = database.item_text(database.resource_item(resource))
    assert isinstance(source, ItemText), f'{resource.ref.path} was written as UTF-8, so it decodes'
    return source


def _resource_context(database: Database) -> SkillResourceContext:
    """The context of `REVIEW`'s one resource, typed as the protocol, so the type checker holds the class to it.

    Args:
        database: The database the resource is read from.
    """
    return DatabaseItemContext(database, _resource_text(database))


def _skill_context(database: Database) -> SkillContext:
    """The context of `REVIEW`, typed as the protocol, so the type checker holds the class to it.

    Args:
        database: The database `REVIEW` is read from.
    """
    return DatabaseItemContext(database, _skill_item(database))


def _scanned(root: Path) -> Database:
    """A database over a scan of a real tree holding what `_snapshot` holds, so the scope covers `docs/` and the skill.

    `Snapshot.from_tree` scans nothing, so no path is in its scope; asking what the snapshot holds at a path needs a
    scan.

    Args:
        root: Directory the tree is written into, as the repository root.
    """
    _write_tree(root, _tree())
    return Database.from_snapshot(take_snapshot(root, SNAPSHOT_SCOPE))


def _write_tree(directory: Path, tree: FileTree) -> None:
    """Write a tree of files under a directory, a nested mapping a directory each, as `Snapshot.from_tree` reads one.

    Args:
        directory: The directory the tree's entries are written into; created if absent.
        tree: Each entry's name, mapped to a file's bytes or to the tree of a directory.
    """
    directory.mkdir(parents=True, exist_ok=True)
    for name, entry in tree.items():
        match entry:
            case bytes():
                (directory / name).write_bytes(entry)
            case Mapping():
                _write_tree(directory / name, entry)
            case _:
                assert_never(entry)


@pytest.mark.it
class TestDatabaseItemContextOverADocument:
    def test_filename_with_a_document_returns_the_filename_of_its_ref(self) -> None:
        #: Given
        context = _document_context(Database.from_snapshot(_snapshot()))

        #: When
        filename = context.filename()

        #: Then
        assert filename == AspectFilename.parse('python-typing'), 'the filename is read from the ref'

    def test_frontmatter_with_a_document_returns_the_frontmatter_query(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = _document_context(database)

        #: When
        frontmatter = context.frontmatter()

        #: Then
        assert frontmatter is database.item_frontmatter(_document_item(database)), (
            'the frontmatter is the value the database memoizes, not one the context parsed again'
        )

    def test_schema_problems_with_a_document_returns_the_schema_problems_query(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = _document_context(database)

        #: When
        schema_problems = context.schema_problems()

        #: Then
        assert schema_problems is database.item_schema_problems(_document_item(database)), (
            'the problems are the ones the database memoizes, not ones the context validated again'
        )
        assert schema_problems != (), 'the corpus schema rejects the `owner` the document writes as a number'

    def test_frontmatter_owner_with_a_document_returns_its_filename_and_corpus_specification(self) -> None:
        #: Given
        context = _document_context(Database.from_snapshot(_snapshot()))

        #: When
        owner = context.frontmatter_owner()

        #: Then
        assert owner == DocumentFrontmatterOwner(filename=AspectFilename.parse('python-typing'), spec=CORPUS_SPEC), (
            "the owner names the document's filename and its corpus's structure specification"
        )

    def test_parse_with_a_document_returns_the_parse_query(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = _document_context(database)

        #: When
        parsed = context.parse()

        #: Then
        assert parsed is database.item_parse(_document_item(database)), (
            'the parse is the one the database memoizes, not one the context parsed again'
        )

    def test_token_count_with_a_document_returns_the_tokens_of_its_whole_file(self) -> None:
        #: Given
        context = _document_context(Database.from_snapshot(_snapshot()))

        #: When
        tokens = context.token_count()

        #: Then
        assert tokens == count_tokens(TYPING_TEXT), 'the tokens are those the token_count query counts'

    def test_specifications_with_a_document_returns_the_governance_query(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = _document_context(database)

        #: When
        governance = context.specifications()

        #: Then
        assert governance is database.item_governance(MarkdownItemRef(TYPING.path)), (
            'the specifications are the governance query'
        )
        assert len(governance.structure_specs()) == 2, 'the corpus and the python namespace both govern the document'

    def test_corpus_structure_with_a_document_returns_its_corpus_structure_specification(self) -> None:
        #: Given
        context = _document_context(Database.from_snapshot(_snapshot()))

        #: When
        corpus_structure = context.corpus_structure()

        #: Then
        assert corpus_structure.path == CORPUS_SPEC, (
            "the corpus structure specification is the corpus's, not the python namespace's that also governs it"
        )

    def test_link_base_with_a_document_returns_its_own_directory(self) -> None:
        #: Given
        context = _document_context(Database.from_snapshot(_snapshot()))

        #: When
        base = context.link_base()

        #: Then
        assert base == DocumentDirectory(RootRelativePath.parse('docs/code')), (
            "a document's relative links are read from the directory holding it"
        )

    def test_link_targets_with_a_document_returns_the_link_targets_query(self, tmp_path: Path) -> None:
        #: Given
        database = _scanned(tmp_path)
        context = _document_context(database)

        #: When
        targets = context.link_targets()

        #: Then
        assert targets is database.item_link_targets(_document_item(database)), (
            'the targets are the ones the database memoizes, not ones the context looked up again'
        )
        assert dict(targets) == {
            NormalisedLinkPath.parse('../__meta__/code.md'): _link_target('docs/__meta__/code.md', PathLookup.FILE),
            NormalisedLinkPath.parse('gone.md'): _link_target('docs/code/gone.md', PathLookup.MISSING),
            NormalisedLinkPath.parse('../../src/main.py'): _link_target('src/main.py', PathLookup.OUTSIDE_SCOPE),
            NormalisedLinkPath.parse('../../../x.md'): EscapingTarget(),
        }, "each link is read from the document's directory, and the one climbing above the repository escapes"


@pytest.mark.it
class TestDatabaseItemContextOverASkillEntry:
    def test_directory_name_with_a_skill_returns_the_name_it_is_listed_under(self) -> None:
        #: Given
        context = _skill_context(Database.from_snapshot(_snapshot()))

        #: When
        directory_name = context.directory_name()

        #: Then
        assert directory_name == PathComponent.parse('review'), (
            'the name is the listed directory, not the name the frontmatter gives'
        )

    def test_link_target_with_a_listed_directory_returns_none(self) -> None:
        #: Given
        context = _skill_context(Database.from_snapshot(_snapshot()))

        #: When
        link_target = context.link_target()

        #: Then
        assert link_target is None, 'a skill listed as a directory, not a link, leads nowhere else'

    def test_link_target_with_a_linked_directory_returns_where_the_link_leads(self) -> None:
        #: Given
        # What a scan records for `.agents/skills/review -> ../../skills/review`: the link in the skills directory,
        # and the SKILL.md at the resolved path it leads to.
        shipped = from_tree({'.agents': {'skills': {}}, 'skills': {'review': {'SKILL.md': REVIEW_TEXT.encode()}}})
        records: dict[RootRelativePath, EntryRecord] = dict(shipped.records)
        records[RootRelativePath.parse('.agents/skills/review')] = SymlinkRecord(PurePosixPath('../../skills/review'))
        database = Database.from_snapshot(Snapshot(SnapshotRecords(records)))
        context = _skill_context(database)

        #: When
        link_target = context.link_target()

        #: Then
        assert link_target == _location(database).resolves_to, (
            'the link target is where the model locates the listed directory'
        )

    def test_frontmatter_with_a_skill_returns_the_skill_frontmatter_query(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = _skill_context(database)

        #: When
        frontmatter = context.frontmatter()

        #: Then
        assert frontmatter is database.item_frontmatter(_skill_item(database)), (
            'the frontmatter is the value the database memoizes, not one the context parsed again'
        )

    def test_schema_problems_with_a_skill_returns_the_skill_schema_problems_query(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = _skill_context(database)

        #: When
        schema_problems = context.schema_problems()

        #: Then
        assert schema_problems is database.item_skill_schema_problems(_skill_item(database)), (
            'the problems are the ones the database memoizes, not ones the context validated again'
        )
        assert schema_problems != (), 'the Agent Skills specification requires the description the skill lacks'

    def test_frontmatter_owner_with_a_skill_returns_its_directory_name_and_link_target(self) -> None:
        #: Given
        context = _skill_context(Database.from_snapshot(_snapshot()))

        #: When
        owner = context.frontmatter_owner()

        #: Then
        assert owner == SkillFrontmatterOwner(directory_name=PathComponent.parse('review'), link_target=None), (
            'the owner names the directory the skill is listed under, and that it leads nowhere else'
        )

    def test_parse_with_a_skill_returns_the_skill_parse_query(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = _skill_context(database)

        #: When
        parsed = context.parse()

        #: Then
        assert parsed is database.item_parse(_skill_item(database)), (
            'the parse is the one the database memoizes, not one the context parsed again'
        )

    def test_query_with_a_skill_returns_the_answer_the_database_memoizes(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = _skill_context(database)

        #: When
        lines = context.query(skill_line_count)

        #: Then
        assert lines == count_lines(REVIEW_TEXT), 'the lines are those the line-count query counts'
        assert lines == database.query(skill_line_count, _skill_item(database).ref), (
            'the answer is the one the database memoizes, not one the context computed again'
        )

    def test_link_base_with_a_skill_returns_the_skill_directory_an_agent_reaches(self) -> None:
        #: Given
        context = _skill_context(Database.from_snapshot(_snapshot()))

        #: When
        base = context.link_base()

        #: Then
        assert base == SkillRoot(REVIEW.directory), "a SKILL.md's relative links are read from the skill root"

    def test_link_targets_with_a_skill_returns_the_skill_link_targets_query(self, tmp_path: Path) -> None:
        #: Given
        database = _scanned(tmp_path)
        context = _skill_context(database)

        #: When
        targets = context.link_targets()

        #: Then
        assert targets is database.item_link_targets(_skill_item(database)), (
            'the targets are the ones the database memoizes, not ones the context looked up again'
        )
        assert dict(targets) == {
            NormalisedLinkPath.parse('references/checklist.md'): _link_target(
                '.agents/skills/review/references/checklist.md', PathLookup.FILE
            ),
            NormalisedLinkPath.parse('references/gone.md'): _link_target(
                '.agents/skills/review/references/gone.md', PathLookup.MISSING
            ),
            NormalisedLinkPath.parse('../x.md'): EscapingTarget(),
        }, 'each link is read from the skill root, and the one climbing above it escapes'


@pytest.mark.it
class TestDatabaseItemContextOfAResource:
    def test_parse_with_a_resource_returns_the_item_parse_query(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = _resource_context(database)

        #: When
        parsed = context.parse()

        #: Then
        assert parsed is database.item_parse(_resource_text(database)), (
            'the parse is the one the database memoizes, not one the context parsed again'
        )

    def test_link_base_with_a_resource_returns_its_skill_directory(self) -> None:
        #: Given
        context = _resource_context(Database.from_snapshot(_snapshot()))

        #: When
        base = context.link_base()

        #: Then
        assert base == SkillRoot(REVIEW.directory), "a resource's relative links are read from the skill root"

    def test_link_targets_with_a_resource_returns_the_item_link_targets_query(self, tmp_path: Path) -> None:
        #: Given
        database = _scanned(tmp_path)
        context = _resource_context(database)

        #: When
        targets = context.link_targets()

        #: Then
        assert targets is database.item_link_targets(_resource_text(database)), (
            'the targets are the ones the database memoizes, not ones the context looked up again'
        )
        assert dict(targets) == {
            NormalisedLinkPath.parse('SKILL.md'): _link_target('.agents/skills/review/SKILL.md', PathLookup.FILE),
            NormalisedLinkPath.parse('gone.md'): _link_target('.agents/skills/review/gone.md', PathLookup.MISSING),
        }, "a resource's links are read from the skill root, so `SKILL.md` names the skill's own"


@pytest.mark.it
class TestDatabaseItemContextOfASpecification:
    def test_filename_with_a_specification_returns_its_specification_name(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = DatabaseItemContext(database, _spec_item(database))

        #: When
        filename = context.filename()

        #: Then
        assert filename == AspectFilename.parse('code-python'), 'the name is the specification file stem'

    def test_base_with_a_specification_returns_the_specification_its_name_continues(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = DatabaseItemContext(database, _spec_item(database))
        expected = 'code'

        #: When
        base = context.base()

        #: Then
        assert base == expected, 'code-python continues code, the corpus specification beside it'

    def test_parse_with_a_specification_returns_the_item_parse_query(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = DatabaseItemContext(database, _spec_item(database))

        #: When
        parsed = context.parse()

        #: Then
        assert parsed is database.item_parse(_spec_item(database)), 'the parse is the one the database memoizes'

    def test_link_base_with_a_specification_returns_the_meta_directory(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = DatabaseItemContext(database, _spec_item(database))

        #: When
        base = context.link_base()

        #: Then
        assert base == DocumentDirectory(RootRelativePath.parse('docs/__meta__')), 'links are read from docs/__meta__'

    def test_link_targets_with_a_specification_returns_the_item_link_targets_query(self, tmp_path: Path) -> None:
        #: Given
        database = _scanned(tmp_path)
        context = DatabaseItemContext(database, _spec_item(database))

        #: When
        targets = context.link_targets()

        #: Then
        assert dict(targets) == {
            NormalisedLinkPath.parse('code.md'): _link_target('docs/__meta__/code.md', PathLookup.FILE),
            NormalisedLinkPath.parse('gone.md'): _link_target('docs/__meta__/gone.md', PathLookup.MISSING),
        }, 'each link is read from the meta directory the specification sits in'

    def test_frontmatter_owner_with_a_specification_raises_wrong_item_kind(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = DatabaseItemContext(database, _spec_item(database))

        #: When
        with pytest.raises(WrongItemKindError) as exc_info:
            context.frontmatter_owner()

        #: Then
        assert str(SPEC.path) in str(exc_info.value), 'the error names the specification asked'

    def test_schema_problems_with_a_specification_raises_wrong_item_kind(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = DatabaseItemContext(database, _spec_item(database))

        #: When
        with pytest.raises(WrongItemKindError) as exc_info:
            context.schema_problems()

        #: Then
        assert str(SPEC.path) in str(exc_info.value), 'the error names the specification asked'

    def test_specifications_with_a_specification_raises_wrong_item_kind(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = DatabaseItemContext(database, _spec_item(database))

        #: When
        with pytest.raises(WrongItemKindError) as exc_info:
            context.specifications()

        #: Then
        assert str(SPEC.path) in str(exc_info.value), 'the error names the specification asked'


def _outside_symlink(database: Database) -> OutsideSymlink:
    """The one symlink of the skill layout whose chain leaves the repository, as the database's model records it.

    Args:
        database: The database over a snapshot whose skills directory holds one entry linked outside the repository.
    """
    outside_symlinks = database.model().sorted_outside_symlinks
    assert len(outside_symlinks) == 1, 'the snapshot holds one entry linked outside the repository'
    return outside_symlinks[0]


def _symlink_context(database: Database) -> SymlinkContext:
    """The context of the entry linked outside the repository, typed as the protocol, so the type checker holds it.

    Args:
        database: The database whose model records the entry.
    """
    return DatabaseSymlinkContext(_outside_symlink(database))


@pytest.mark.it
class TestDatabaseSymlinkContext:
    def test_leaves_at_with_an_entry_linked_outside_returns_where_the_model_records_it_leaving(self) -> None:
        #: Given
        # What a scan records for `.agents/skills/x -> /elsewhere/x`: the link alone, since nothing outside the root
        # is read.
        records: dict[RootRelativePath, EntryRecord] = dict(_snapshot().records)
        records[RootRelativePath.parse('.agents/skills/x')] = SymlinkRecord(PurePosixPath('/elsewhere/x'))
        database = Database.from_snapshot(Snapshot(SnapshotRecords(records)))
        context = _symlink_context(database)

        #: When
        leaves_at = context.leaves_at()

        #: Then
        assert leaves_at is _outside_symlink(database).leaves_at, (
            'where the chain leaves is the record the model query keeps, not one the context looked up again'
        )
        assert leaves_at == RootExit(RootRelativePath.parse('.agents/skills/x'), PurePosixPath('/elsewhere/x')), (
            'the entry links straight out, so it is the link the chain leaves through, with its target as recorded'
        )


@pytest.mark.it
class TestDatabaseItemContextOverTheOtherKind:
    def test_filename_with_a_skill_entry_raises_wrong_item_kind_error(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = DatabaseItemContext(database, _skill_item(database))

        #: When
        with pytest.raises(WrongItemKindError) as raised:
            context.filename()

        #: Then
        assert REVIEW.path.value.as_posix() in str(raised.value), 'the error names the skill entry asked for a filename'

    def test_directory_name_with_a_document_raises_wrong_item_kind_error(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot())
        context = DatabaseItemContext(database, _document_item(database))

        #: When
        with pytest.raises(WrongItemKindError) as raised:
            context.directory_name()

        #: Then
        assert TYPING.path.value.as_posix() in str(raised.value), 'the error names the document asked for a directory'


@pytest.mark.it
class TestDatabaseCorpusDirectoryContext:
    def test_path_and_reserved_corpus_with_a_recorded_directory_return_what_the_record_holds(self) -> None:
        #: Given
        directory = ReservedCorpusDirectory(RootRelativePath.parse('docs/skills'), CorpusName.parse('skills'))
        context: CorpusDirectoryContext = DatabaseCorpusDirectoryContext(directory)

        #: When
        facts = (context.path(), context.reserved_corpus())

        #: Then
        assert facts == (directory.path, directory.corpus), 'the context reads both facts from the record'
