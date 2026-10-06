"""The database-backed contexts, held to the protocols of `lorecraft.project` they implement.

Each method of `DocumentContext` and `SkillContext` is asked through a value typed as the protocol, over a database
opened on an in-memory snapshot, and compared with what the database's matching query returns; a fact the database
memoizes is the very value the query keeps, so a context computes nothing of its own. The static hold of each class
to its protocol is in `lorecraft.checks.tests.test_context`, where the type-checking gate reaches it.
"""

from pathlib import PurePosixPath
from typing import Final

import pytest

from lorecraft.checks import Database, DocumentText, SkillText
from lorecraft.checks.context import DatabaseDocumentContext, DatabaseSkillContext
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.context import DocumentContext, DocumentFrontmatterOwner, SkillContext, SkillFrontmatterOwner
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.skill import SkillLocation, SkillRef
from lorecraft.project.syntax import count_lines, count_tokens
from lorecraft.vfs import EntryRecord, Snapshot, SymlinkRecord

TYPING: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-typing'))
"""A document of corpus `code` its `python` namespace governs too."""

TYPING_TEXT: Final[str] = '---\nname: python-typing\nowner: 7\n---\n# Typing\n\n## Rule\n\nAnnotate every signature.\n'
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

REVIEW_TEXT: Final[str] = '---\nname: reviewer\n---\n# Review\n\nRead the diff.\n'
"""The `SKILL.md` of `REVIEW`: a frontmatter missing the `description` the Agent Skills specification requires."""


def _snapshot() -> Snapshot:
    """A snapshot of corpus `code`, with a `python` namespace, holding `TYPING` and the skill `REVIEW`."""
    return Snapshot.from_tree(
        {
            '.agents': {'skills': {'review': {'SKILL.md': REVIEW_TEXT.encode()}}},
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
    )


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


def _skill_context(database: Database) -> SkillContext:
    """The context of `REVIEW`, typed as the protocol, so the type checker holds the class to it.

    Args:
        database: The database `REVIEW` is read from.
    """
    return DatabaseSkillContext(database, _skill_text(database), _location(database))


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
