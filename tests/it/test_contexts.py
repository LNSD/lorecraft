"""The database-backed contexts, held to the protocols of `lorecraft.project` they implement.

Each method of `DocumentContext`, `SkillContext` and `SkillResourceContext` is asked through a value typed as the
protocol, over a database opened on an in-memory snapshot, and compared with what the database's matching query
returns; a fact the database memoizes is the very value the query keeps, so a context computes nothing of its own.
The static hold of each class to its protocol is in `lorecraft.project.database.tests.test_context`, where the
type-checking gate reaches it.
"""

from pathlib import Path, PurePosixPath
from typing import Final

import pytest

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.context import (
    DocumentContext,
    DocumentFrontmatterOwner,
    SkillContext,
    SkillFrontmatterOwner,
    SkillResourceContext,
)
from lorecraft.project.corpus import CorpusName
from lorecraft.project.database import (
    Database,
    DatabaseDocumentContext,
    DatabaseSkillContext,
    DatabaseSkillResourceContext,
    DocumentText,
    SkillResourceText,
    SkillText,
)
from lorecraft.project.document import DocumentRef
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.link_target import DocumentDirectory, PathLookup, SkillRoot
from lorecraft.project.skill import SkillLocation, SkillRef
from lorecraft.project.syntax import count_lines, count_tokens
from lorecraft.vfs import EntryRecord, FileTree, Snapshot, SymlinkRecord, take_snapshot

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

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
"""Where the corpus structure specification lies."""

REVIEW: Final[SkillRef] = SkillRef(RootRelativePath.parse('.agents/skills/review'))
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
                'code.structure.json': CORPUS_STRUCTURE,
                'code-python.md': b'# Code Python\n',
                'code-python.structure.json': b'{"tokens": 200}',
            },
            'code': {'python-typing.md': TYPING_TEXT.encode()},
        },
    }


def _snapshot() -> Snapshot:
    """A snapshot of `_tree`, built in memory, so no path is in its scope."""
    return Snapshot.from_tree(_tree())


def _document_text(database: Database) -> DocumentText:
    """The witness of `TYPING`, as the database decodes it.

    Args:
        database: The database `TYPING` is decoded by.
    """
    source = database.text(TYPING)
    assert isinstance(source, DocumentText), f'{TYPING.path} was written as UTF-8, so it decodes'
    return source


def _document_context(database: Database) -> DocumentContext:
    """The context of `TYPING`, typed as the protocol, so the type checker holds the class to it.

    Args:
        database: The database `TYPING` is read from.
    """
    governance = database.model().find_governance(TYPING)
    assert governance is not None, f'{TYPING.path} is in the corpus `code`, so specifications govern it'
    corpus_structure = governance.corpus_spec.structure
    assert corpus_structure is not None, 'the corpus `code` states a structure specification'
    return DatabaseDocumentContext(database, _document_text(database), governance, corpus_structure)


def _skill_text(database: Database) -> SkillText:
    """The witness of `REVIEW`'s `SKILL.md`, as the database decodes it.

    Args:
        database: The database the `SKILL.md` is decoded by.
    """
    source = database.skill_text(REVIEW)
    assert isinstance(source, SkillText), f'{REVIEW.path} was written as UTF-8, so it decodes'
    return source


def _location(database: Database) -> SkillLocation:
    """Where the database's model locates `REVIEW`.

    Args:
        database: The database whose model lists the skill.
    """
    location = database.model().find_skill_location(REVIEW.directory)
    assert location is not None, f'the model lists the skill {REVIEW.directory}'
    return location


def _resource_text(database: Database) -> SkillResourceText:
    """The witness of `REVIEW`'s one resource, as the database decodes it at the file its listing locates.

    Args:
        database: The database the resource is listed and decoded by.
    """
    (resource,) = database.skill_resources(_location(database)).resources
    source = database.skill_resource_text(resource)
    assert isinstance(source, SkillResourceText), f'{resource.ref.path} was written as UTF-8, so it decodes'
    return source


def _resource_context(database: Database) -> SkillResourceContext:
    """The context of `REVIEW`'s one resource, typed as the protocol, so the type checker holds the class to it.

    Args:
        database: The database the resource is read from.
    """
    return DatabaseSkillResourceContext(database, _resource_text(database))


def _skill_context(database: Database) -> SkillContext:
    """The context of `REVIEW`, typed as the protocol, so the type checker holds the class to it.

    Args:
        database: The database `REVIEW` is read from.
    """
    return DatabaseSkillContext(database, _skill_text(database), _location(database))


def _scanned(root: Path) -> Database:
    """A database over a scan of a real tree holding what `_snapshot` holds, so the scope covers `docs/` and the skill.

    `Snapshot.from_tree` scans nothing, so no path is in its scope; asking what the snapshot holds at a path needs a
    scan.

    Args:
        root: Directory the tree is written into, as the repository root.
    """
    _write_tree(root, _tree())
    return Database(take_snapshot(root, SNAPSHOT_SCOPE))


def _write_tree(directory: Path, tree: FileTree) -> None:
    """Write a tree of files under a directory, a nested mapping a directory each, as `Snapshot.from_tree` reads one.

    Args:
        directory: The directory the tree's entries are written into; created if absent.
        tree: Each entry's name, mapped to a file's bytes or to the tree of a directory.
    """
    directory.mkdir(parents=True, exist_ok=True)
    for name, entry in tree.items():
        if isinstance(entry, bytes):
            (directory / name).write_bytes(entry)
        else:
            _write_tree(directory / name, entry)


@pytest.mark.it
class TestDatabaseDocumentContext:
    def test_filename_with_a_document_returns_the_filename_of_its_ref(self) -> None:
        #: Given
        context = _document_context(Database(_snapshot()))

        #: When
        filename = context.filename()

        #: Then
        assert filename == AspectFilename.parse('python-typing'), 'the filename is read from the ref'

    def test_frontmatter_with_a_document_returns_the_frontmatter_query(self) -> None:
        #: Given
        database = Database(_snapshot())
        context = _document_context(database)

        #: When
        frontmatter = context.frontmatter()

        #: Then
        assert frontmatter is database.frontmatter(_document_text(database)), (
            'the frontmatter is the value the database memoizes, not one the context parsed again'
        )

    def test_schema_problems_with_a_document_returns_the_schema_problems_query(self) -> None:
        #: Given
        database = Database(_snapshot())
        context = _document_context(database)

        #: When
        schema_problems = context.schema_problems()

        #: Then
        assert schema_problems is database.schema_problems(_document_text(database)), (
            'the problems are the ones the database memoizes, not ones the context validated again'
        )
        assert schema_problems != (), 'the corpus schema rejects the `owner` the document writes as a number'

    def test_frontmatter_owner_with_a_document_returns_its_filename_and_corpus_specification(self) -> None:
        #: Given
        context = _document_context(Database(_snapshot()))

        #: When
        owner = context.frontmatter_owner()

        #: Then
        assert owner == DocumentFrontmatterOwner(filename=AspectFilename.parse('python-typing'), spec=CORPUS_SPEC), (
            "the owner names the document's filename and its corpus's structure specification"
        )

    def test_parse_with_a_document_returns_the_parse_query(self) -> None:
        #: Given
        database = Database(_snapshot())
        context = _document_context(database)

        #: When
        parsed = context.parse()

        #: Then
        assert parsed is database.parse(_document_text(database)), (
            'the parse is the one the database memoizes, not one the context parsed again'
        )

    def test_tokens_with_a_document_returns_the_tokens_of_its_whole_file(self) -> None:
        #: Given
        context = _document_context(Database(_snapshot()))

        #: When
        tokens = context.tokens()

        #: Then
        assert tokens == UnsignedInt(count_tokens(TYPING_TEXT)), 'the tokens are those the tokens query counts'

    def test_lines_with_a_document_returns_the_lines_of_its_whole_file(self) -> None:
        #: Given
        context = _document_context(Database(_snapshot()))

        #: When
        lines = context.lines()

        #: Then
        assert lines == UnsignedInt(count_lines(TYPING_TEXT)), 'the lines are those the document-lines query counts'

    def test_specifications_with_a_document_returns_the_governance_the_model_finds(self) -> None:
        #: Given
        database = Database(_snapshot())
        context = _document_context(database)

        #: When
        governance = context.specifications()

        #: Then
        assert governance == database.model().find_governance(TYPING), (
            'the specifications are the governance the model finds for the document'
        )
        assert len(governance.structure_specs()) == 2, 'the corpus and the python namespace both govern the document'

    def test_outline_divergences_with_a_document_returns_the_outline_divergences_query(self) -> None:
        #: Given
        database = Database(_snapshot())
        context = _document_context(database)

        #: When
        divergences = context.outline_divergences()

        #: Then
        assert divergences is database.outline_divergences(_document_text(database)), (
            'the divergences are the ones the database memoizes, not ones the context matched again'
        )
        assert divergences != (), 'the corpus outline states a section the document lacks'

    def test_link_base_with_a_document_returns_its_own_directory(self) -> None:
        #: Given
        context = _document_context(Database(_snapshot()))

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
        assert targets is database.link_targets(_document_text(database)), (
            'the targets are the ones the database memoizes, not ones the context looked up again'
        )
        assert dict(targets) == {
            PurePosixPath('../__meta__/code.md'): PathLookup.PRESENT,
            PurePosixPath('gone.md'): PathLookup.MISSING,
            PurePosixPath('../../src/main.py'): PathLookup.OUTSIDE_SCOPE,
        }, "each link is read from the document's directory, and the one climbing above the repository has no entry"


@pytest.mark.it
class TestDatabaseSkillContext:
    def test_directory_name_with_a_skill_returns_the_name_it_is_listed_under(self) -> None:
        #: Given
        context = _skill_context(Database(_snapshot()))

        #: When
        directory_name = context.directory_name()

        #: Then
        assert directory_name == 'review', 'the name is the listed directory, not the name the frontmatter gives'

    def test_link_target_with_a_listed_directory_returns_none(self) -> None:
        #: Given
        context = _skill_context(Database(_snapshot()))

        #: When
        link_target = context.link_target()

        #: Then
        assert link_target is None, 'a skill listed as a directory, not a link, leads nowhere else'

    def test_link_target_with_a_linked_directory_returns_where_the_link_leads(self) -> None:
        #: Given
        # What a scan records for `.agents/skills/review -> ../../skills/review`: the link in the skills directory,
        # and the SKILL.md at the resolved path it leads to.
        shipped = Snapshot.from_tree(
            {'.agents': {'skills': {}}, 'skills': {'review': {'SKILL.md': REVIEW_TEXT.encode()}}}
        )
        records: dict[RootRelativePath, EntryRecord] = dict(shipped.records)
        records[RootRelativePath.parse('.agents/skills/review')] = SymlinkRecord(PurePosixPath('../../skills/review'))
        database = Database(Snapshot(FrozenMapping(records)))
        context = _skill_context(database)

        #: When
        link_target = context.link_target()

        #: Then
        assert link_target == _location(database).resolves_to, (
            'the link target is where the model locates the listed directory'
        )

    def test_frontmatter_with_a_skill_returns_the_skill_frontmatter_query(self) -> None:
        #: Given
        database = Database(_snapshot())
        context = _skill_context(database)

        #: When
        frontmatter = context.frontmatter()

        #: Then
        assert frontmatter is database.skill_frontmatter(_skill_text(database)), (
            'the frontmatter is the value the database memoizes, not one the context parsed again'
        )

    def test_schema_problems_with_a_skill_returns_the_skill_schema_problems_query(self) -> None:
        #: Given
        database = Database(_snapshot())
        context = _skill_context(database)

        #: When
        schema_problems = context.schema_problems()

        #: Then
        assert schema_problems is database.skill_schema_problems(_skill_text(database)), (
            'the problems are the ones the database memoizes, not ones the context validated again'
        )
        assert schema_problems != (), 'the Agent Skills specification requires the description the skill lacks'

    def test_frontmatter_owner_with_a_skill_returns_its_directory_name_and_link_target(self) -> None:
        #: Given
        context = _skill_context(Database(_snapshot()))

        #: When
        owner = context.frontmatter_owner()

        #: Then
        assert owner == SkillFrontmatterOwner(directory_name='review', link_target=None), (
            'the owner names the directory the skill is listed under, and that it leads nowhere else'
        )

    def test_parse_with_a_skill_returns_the_skill_parse_query(self) -> None:
        #: Given
        database = Database(_snapshot())
        context = _skill_context(database)

        #: When
        parsed = context.parse()

        #: Then
        assert parsed is database.skill_parse(_skill_text(database)), (
            'the parse is the one the database memoizes, not one the context parsed again'
        )

    def test_lines_with_a_skill_returns_the_lines_of_its_whole_skill_file(self) -> None:
        #: Given
        context = _skill_context(Database(_snapshot()))

        #: When
        lines = context.lines()

        #: Then
        assert lines == UnsignedInt(count_lines(REVIEW_TEXT)), 'the lines are those the skill-lines query counts'

    def test_link_base_with_a_skill_returns_the_skill_directory_an_agent_reaches(self) -> None:
        #: Given
        context = _skill_context(Database(_snapshot()))

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
        assert targets is database.skill_link_targets(_skill_text(database)), (
            'the targets are the ones the database memoizes, not ones the context looked up again'
        )
        assert dict(targets) == {
            PurePosixPath('references/checklist.md'): PathLookup.PRESENT,
            PurePosixPath('references/gone.md'): PathLookup.MISSING,
        }, 'each link is read from the skill root, and the one climbing above it has no entry'


@pytest.mark.it
class TestDatabaseSkillResourceContext:
    def test_parse_with_a_resource_returns_the_skill_resource_parse_query(self) -> None:
        #: Given
        database = Database(_snapshot())
        context = _resource_context(database)

        #: When
        parsed = context.parse()

        #: Then
        assert parsed is database.skill_resource_parse(_resource_text(database)), (
            'the parse is the one the database memoizes, not one the context parsed again'
        )

    def test_link_base_with_a_resource_returns_its_skill_directory(self) -> None:
        #: Given
        context = _resource_context(Database(_snapshot()))

        #: When
        base = context.link_base()

        #: Then
        assert base == SkillRoot(REVIEW.directory), "a resource's relative links are read from the skill root"

    def test_link_targets_with_a_resource_returns_the_skill_resource_link_targets_query(self, tmp_path: Path) -> None:
        #: Given
        database = _scanned(tmp_path)
        context = _resource_context(database)

        #: When
        targets = context.link_targets()

        #: Then
        assert targets is database.skill_resource_link_targets(_resource_text(database)), (
            'the targets are the ones the database memoizes, not ones the context looked up again'
        )
        assert dict(targets) == {
            PurePosixPath('SKILL.md'): PathLookup.PRESENT,
            PurePosixPath('gone.md'): PathLookup.MISSING,
        }, "a resource's links are read from the skill root, so `SKILL.md` names the skill's own"
