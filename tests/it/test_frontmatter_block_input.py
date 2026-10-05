"""The frontmatter-block input, built from a database's frontmatter queries for one decoded document or skill.

A document's governance comes from the model, so the input is tested over a database opened on an in-memory
snapshot: a document governed by a corpus and a namespace schema, and one no schema governs. The builder locates the
line of every fact a rule reports at, the `name` and each repeated key, so those lines are tested here too. A skill's
link target is derived by the runner from the location the model hands out, and handed to the builder as it is.
"""

from typing import Final

import pytest

from lorecraft.checks import Database, DocumentText, SkillText
from lorecraft.checks.inputs import (
    Ungoverned,
    build_document_frontmatter_block_input,
    build_skill_frontmatter_block_input,
)
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.skill import SkillRef
from lorecraft.project.syntax import FrontmatterNode, LineNumber, MissingFrontmatter
from lorecraft.rules.inputs import (
    DocumentFrontmatterOwner,
    FrontmatterBlockInput,
    FrontmatterFields,
    NameField,
    RepeatedKey,
    SkillFrontmatterOwner,
)
from lorecraft.vfs import ResolvedPath, Snapshot

TYPING: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-typing'))
"""A document of corpus `code` its `python` namespace governs too."""

TYPING_TEXT: Final[str] = '---\nname: python-typing\n---\n# Typing\n'
"""The text of `TYPING`, whose `name` is on line 2."""

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
"""The corpus structure specification."""

REVIEW: Final[SkillRef] = SkillRef(RootRelativePath.parse('.agents/skills/review'))
"""A skill an agent reaches under `.agents/skills`."""

REVIEW_TEXT: Final[str] = '---\nname: review\n---\n# Review\n'
"""The text of `REVIEW`'s `SKILL.md`, whose `name` is on line 2."""

OBJECT_SCHEMA: Final[bytes] = b'{"frontmatter": {"type": "object"}}'
"""A structure specification whose frontmatter schema accepts any mapping."""

BUDGET_ONLY: Final[bytes] = b'{"tokens": 100}'
"""A structure specification that states no frontmatter schema."""


class CountingDatabase(Database):
    """A database that records each document whose frontmatter it is asked for, then parses it as usual."""

    def __init__(self, snapshot: Snapshot) -> None:
        """Open the database on the snapshot, with no frontmatter asked for yet.

        Args:
            snapshot: The revision the database reads.
        """
        super().__init__(snapshot)
        self.parsed_frontmatters: list[DocumentRef] = []

    def frontmatter(self, source: DocumentText) -> FrontmatterNode:
        """Record the document, then parse its frontmatter.

        Args:
            source: The decoded document whose frontmatter is parsed, recorded by its ref first.
        """
        self.parsed_frontmatters.append(source.ref)
        return super().frontmatter(source)


def _document_snapshot(corpus_spec: bytes, namespace_spec: bytes, *, typing: str = TYPING_TEXT) -> Snapshot:
    """A snapshot of corpus `code`, with a `python` namespace, holding the one document `TYPING`.

    Args:
        corpus_spec: Bytes of the corpus structure specification.
        namespace_spec: Bytes of the `python` namespace structure specification.
        typing: The text of `TYPING`.
    """
    return Snapshot.from_tree(
        {
            'docs': {
                '__meta__': {
                    'code.md': b'# Code\n',
                    'code.structure.json': corpus_spec,
                    'code-python.md': b'# Code Python\n',
                    'code-python.structure.json': namespace_spec,
                },
                'code': {'python-typing.md': typing.encode()},
            }
        }
    )


def _document_text(database: Database, ref: DocumentRef) -> DocumentText:
    """The witness of a document the test wrote as UTF-8, as the database decodes it.

    Args:
        database: The database the document is decoded by.
        ref: A document whose bytes are UTF-8.
    """
    source = database.text(ref)
    assert isinstance(source, DocumentText), f'{ref.path} was written as UTF-8, so it decodes'
    return source


def _skill_text(database: Database, ref: SkillRef) -> SkillText:
    """The witness of a skill whose `SKILL.md` the test wrote as UTF-8, as the database decodes it.

    Args:
        database: The database the `SKILL.md` is decoded by.
        ref: A skill whose `SKILL.md` bytes are UTF-8.
    """
    source = database.skill_text(ref)
    assert isinstance(source, SkillText), f'{ref.path} was written as UTF-8, so it decodes'
    return source


def _governed_input(typing: str) -> FrontmatterBlockInput:
    """The frontmatter-block input of `TYPING`, written with this text, under a corpus frontmatter schema.

    Args:
        typing: The text of `TYPING`.
    """
    database = Database(_document_snapshot(OBJECT_SCHEMA, BUDGET_ONLY, typing=typing))
    subject = build_document_frontmatter_block_input(database, _document_text(database, TYPING))
    assert isinstance(subject, FrontmatterBlockInput), 'a corpus frontmatter schema governs the document'
    return subject


@pytest.mark.it
class TestBuildDocumentFrontmatterBlockInput:
    def test_build_document_frontmatter_block_input_with_a_corpus_schema_holds_the_located_name_and_filename(
        self,
    ) -> None:
        #: Given
        database = Database(_document_snapshot(OBJECT_SCHEMA, BUDGET_ONLY))
        source = _document_text(database, TYPING)

        #: When
        subject = build_document_frontmatter_block_input(database, source)

        #: Then
        assert subject == FrontmatterBlockInput(
            frontmatter=FrontmatterFields(
                name=NameField(value='python-typing', line=LineNumber.from_int(2)), repeated_keys=()
            ),
            owner=DocumentFrontmatterOwner(filename=TYPING.filename, spec=CORPUS_SPEC),
        ), 'the corpus schema governs the block, the `name` is located on its line, and the filename rides along'

    def test_build_document_frontmatter_block_input_with_a_namespace_schema_too_names_the_corpus_spec(self) -> None:
        #: Given
        database = Database(_document_snapshot(OBJECT_SCHEMA, OBJECT_SCHEMA))
        source = _document_text(database, TYPING)

        #: When
        subject = build_document_frontmatter_block_input(database, source)

        #: Then
        assert subject == FrontmatterBlockInput(
            frontmatter=FrontmatterFields(
                name=NameField(value='python-typing', line=LineNumber.from_int(2)), repeated_keys=()
            ),
            owner=DocumentFrontmatterOwner(filename=TYPING.filename, spec=CORPUS_SPEC),
        ), "a namespace schema only narrows the corpus's, so the corpus specification states the block's rules"

    def test_build_document_frontmatter_block_input_with_only_a_namespace_schema_is_ungoverned(self) -> None:
        #: Given
        database = Database(_document_snapshot(BUDGET_ONLY, OBJECT_SCHEMA))
        source = _document_text(database, TYPING)

        #: When
        subject = build_document_frontmatter_block_input(database, source)

        #: Then
        assert subject == Ungoverned(), 'a namespace narrows a base schema, it cannot supply one'

    def test_build_document_frontmatter_block_input_with_no_schema_never_parses_the_frontmatter(self) -> None:
        #: Given
        database = CountingDatabase(_document_snapshot(BUDGET_ONLY, b'{"tokens": 50}'))
        source = _document_text(database, TYPING)

        #: When
        build_document_frontmatter_block_input(database, source)

        #: Then
        assert database.parsed_frontmatters == [], 'governance is read first, so an ungoverned block is never parsed'

    def test_build_document_frontmatter_block_input_with_a_document_in_no_corpus_is_ungoverned(self) -> None:
        #: Given
        snapshot = Snapshot.from_tree(
            {
                'docs': {
                    '__meta__': {'code.md': b'# Code\n', 'code.structure.json': OBJECT_SCHEMA},
                    'blog': {'launch.md': TYPING_TEXT.encode()},
                }
            }
        )
        database = Database(snapshot)
        launch = DocumentRef(CorpusName.parse('blog'), AspectFilename.parse('launch'))
        source = _document_text(database, launch)

        #: When
        subject = build_document_frontmatter_block_input(database, source)

        #: Then
        assert subject == Ungoverned(), 'no specification governs a document in no corpus the model holds'

    def test_build_document_frontmatter_block_input_with_no_block_passes_the_outcome_through(self) -> None:
        #: When
        subject = _governed_input('# Typing\n')

        #: Then
        assert subject.frontmatter == MissingFrontmatter(), 'a block that holds no mapping is passed on as it reads'

    def test_build_document_frontmatter_block_input_with_a_key_written_three_times_locates_each_repetition(
        self,
    ) -> None:
        #: When
        subject = _governed_input(
            '---\nname: python-typing\nname: python-typing\nmetadata:\n  name: inner\nname: other\n---\n'
        )

        #: Then
        assert subject.frontmatter == FrontmatterFields(
            name=NameField(value='other', line=LineNumber.from_int(6)),
            repeated_keys=(
                RepeatedKey(key='name', line=LineNumber.from_int(3), first_line=LineNumber.from_int(2)),
                RepeatedKey(key='name', line=LineNumber.from_int(6), first_line=LineNumber.from_int(2)),
            ),
        ), (
            'each repetition points back at the first occurrence, a nested key repeats no top-level one, and the '
            '`name` is the last value, at the last line'
        )

    def test_build_document_frontmatter_block_input_with_no_name_holds_none(self) -> None:
        #: When
        subject = _governed_input('---\ntitle: Typing\n---\n')

        #: Then
        assert subject.frontmatter == FrontmatterFields(name=None, repeated_keys=()), 'a mapping may hold no `name`'


@pytest.mark.it
class TestBuildSkillFrontmatterBlockInput:
    def test_build_skill_frontmatter_block_input_with_no_link_holds_the_listed_directory_name(self) -> None:
        #: Given
        database = Database(Snapshot.from_tree({'.agents': {'skills': {'review': {'SKILL.md': REVIEW_TEXT.encode()}}}}))
        source = _skill_text(database, REVIEW)

        #: When
        subject = build_skill_frontmatter_block_input(database, source, None)

        #: Then
        assert subject == FrontmatterBlockInput(
            frontmatter=FrontmatterFields(
                name=NameField(value='review', line=LineNumber.from_int(2)), repeated_keys=()
            ),
            owner=SkillFrontmatterOwner(directory_name='review', link_target=None),
        ), 'a skill needs no specification in the repository, and is held to the directory it is listed under'

    def test_build_skill_frontmatter_block_input_with_a_link_target_holds_it(self) -> None:
        #: Given
        database = Database(Snapshot.from_tree({'.agents': {'skills': {'review': {'SKILL.md': REVIEW_TEXT.encode()}}}}))
        source = _skill_text(database, REVIEW)
        shipped = ResolvedPath(RootRelativePath.parse('skills/code-review'))

        #: When
        subject = build_skill_frontmatter_block_input(database, source, shipped)

        #: Then
        assert subject.owner == SkillFrontmatterOwner(directory_name='review', link_target=shipped), (
            'the name expected is the listed one, and the directory a link leads to only rides along'
        )
