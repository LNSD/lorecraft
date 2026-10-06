"""The `schema_problems` and `skill_schema_problems` queries, for one decoded document or skill.

A document's schemas come from the model's governance and a skill's is the Agent Skills specification, so the queries
are tested over a database opened on an in-memory snapshot: a document governed by a corpus and a namespace schema, an
ungoverned one, one without a block, and a skill. How each problem is found and placed on its line is
`locate_schema_problems`'s, tested on its own beside it.
"""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.database import Database, DocumentText, SkillText
from lorecraft.project.document import DocumentRef
from lorecraft.project.schemas import (
    AgentSkillsSchema,
    LocatedProblem,
    MissingFieldProblem,
    SchemaProblems,
    StructureSpecSchema,
    UnknownFieldProblem,
    WrongTypeProblem,
)
from lorecraft.project.skill import SkillRef
from lorecraft.project.syntax import FrontmatterNode, LineNumber
from lorecraft.vfs import Snapshot

TYPING: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-typing'))
"""A document of corpus `code` its `python` namespace governs too."""

REVIEW: Final[SkillRef] = SkillRef(RootRelativePath.parse('.agents/skills/review'))
"""A skill an agent reaches under `.agents/skills`."""

CORPUS_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
"""The corpus structure specification."""

NAMESPACE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code-python.structure.json')
"""The `python` namespace structure specification."""

REQUIRE_STATUS: Final[bytes] = b'{"frontmatter": {"type": "object", "required": ["status"]}}'
"""A structure specification whose frontmatter schema requires `status`."""

REQUIRE_OWNER: Final[bytes] = b'{"frontmatter": {"type": "object", "required": ["owner"]}}'
"""A structure specification whose frontmatter schema requires `owner`."""

STRING_DESCRIPTION: Final[bytes] = (
    b'{"frontmatter": {"type": "object", "properties": {"description": {"type": "string"}}}}'
)
"""A structure specification whose frontmatter schema requires `description` to be a string."""


class FrontmatterReadingDatabase(Database):
    """A database that records each document whose frontmatter it is asked for, then reads it as usual."""

    def __init__(self, snapshot: Snapshot) -> None:
        """Open the database on the snapshot, with no frontmatter read yet.

        Args:
            snapshot: The revision the database reads.
        """
        super().__init__(snapshot)
        self.read: list[DocumentRef] = []

    def frontmatter(self, source: DocumentText) -> FrontmatterNode:
        """Record the document, then read its frontmatter.

        Args:
            source: The decoded document whose frontmatter is read, recorded by its ref first.
        """
        self.read.append(source.ref)
        return super().frontmatter(source)


def _snapshot(corpus_spec: bytes, namespace_spec: bytes, *, typing: bytes, review: bytes = b'') -> Snapshot:
    """A snapshot of corpus `code`, with a `python` namespace, holding the document `TYPING` and the skill `REVIEW`.

    Args:
        corpus_spec: Bytes of the corpus structure specification.
        namespace_spec: Bytes of the `python` namespace structure specification.
        typing: Bytes of `TYPING`.
        review: Bytes of `REVIEW`'s `SKILL.md`.
    """
    return Snapshot.from_tree(
        {
            '.agents': {'skills': {'review': {'SKILL.md': review}}},
            'docs': {
                '__meta__': {
                    'code.md': b'# Code\n',
                    'code.structure.json': corpus_spec,
                    'code-python.md': b'# Code Python\n',
                    'code-python.structure.json': namespace_spec,
                },
                'code': {'python-typing.md': typing},
            },
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


@pytest.mark.it
class TestSchemaProblems:
    def test_schema_problems_of_a_governed_document_holds_each_schema_problems_on_their_lines(self) -> None:
        #: Given
        # `description` is on line 3 and of the wrong type; `status` is missing, so it is on no line
        typing = b'---\nname: python-typing\ndescription: 3\n---\n# Typing\n'
        database = Database(_snapshot(REQUIRE_STATUS, STRING_DESCRIPTION, typing=typing))
        source = _document_text(database, TYPING)

        #: When
        found = database.schema_problems(source)

        #: Then
        assert found == (
            SchemaProblems(
                source=StructureSpecSchema(spec=CORPUS_SPEC),
                problems=(
                    LocatedProblem(
                        problem=MissingFieldProblem('status', "'status' is a required property"),
                        line=LineNumber.from_int(1),
                    ),
                ),
            ),
            SchemaProblems(
                source=StructureSpecSchema(spec=NAMESPACE_SPEC),
                problems=(
                    LocatedProblem(
                        problem=WrongTypeProblem('description', "3 is not of type 'string'"),
                        line=LineNumber.from_int(3),
                    ),
                ),
            ),
        ), 'the governing schemas come from the model, the frontmatter from its query, each problem on its line'

    def test_schema_problems_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        typing = b'---\nname: python-typing\n---\n# Typing\n'
        database = FrontmatterReadingDatabase(_snapshot(REQUIRE_STATUS, REQUIRE_OWNER, typing=typing))
        source = _document_text(database, TYPING)
        first = database.schema_problems(source)

        #: When
        second = database.schema_problems(source)

        #: Then
        assert second is first, 'the schemas are applied once per database, then shared by every rule'
        assert database.read == [TYPING], 'the frontmatter is read once, for the first call'

    def test_schema_problems_with_no_frontmatter_schema_holds_none(self) -> None:
        #: Given
        # the namespace states a schema, but a namespace narrows the corpus, which states none
        database = Database(_snapshot(b'{"tokens": 40}', STRING_DESCRIPTION, typing=b'---\ndescription: 3\n---\n'))
        source = _document_text(database, TYPING)

        #: When
        found = database.schema_problems(source)

        #: Then
        assert found == (), 'no corpus schema states a frontmatter schema, so no schema is applied'

    def test_schema_problems_with_no_frontmatter_schema_never_reads_the_frontmatter(self) -> None:
        #: Given
        # the namespace states a schema, but a namespace narrows the corpus, which states none
        database = FrontmatterReadingDatabase(
            _snapshot(b'{"tokens": 40}', STRING_DESCRIPTION, typing=b'---\ndescription: 3\n---\n')
        )
        source = _document_text(database, TYPING)

        #: When
        database.schema_problems(source)

        #: Then
        assert database.read == [], (
            'the schemas are read first, so a document no schema governs never has its block read'
        )

    def test_schema_problems_with_a_document_without_a_block_holds_none(self) -> None:
        #: Given
        database = Database(_snapshot(REQUIRE_STATUS, STRING_DESCRIPTION, typing=b'# Typing\n'))
        source = _document_text(database, TYPING)

        #: When
        found = database.schema_problems(source)

        #: Then
        assert found == (), (
            'the document is governed, but no schema can hold a missing block: the block rules report it'
        )

    def test_schema_problems_with_a_document_in_no_corpus_holds_none(self) -> None:
        #: Given
        # the code corpus states a schema, but `docs/blog/` has no corpus spec, so the model holds no `blog` corpus
        snapshot = Snapshot.from_tree(
            {
                'docs': {
                    '__meta__': {'code.md': b'# Code\n', 'code.structure.json': REQUIRE_STATUS},
                    'blog': {'launch.md': b'---\nname: launch\n---\n# Launch\n'},
                }
            }
        )
        database = Database(snapshot)
        source = _document_text(database, DocumentRef(CorpusName.parse('blog'), AspectFilename.parse('launch')))

        #: When
        found = database.schema_problems(source)

        #: Then
        assert found == (), 'no specification governs a document in no corpus the model holds'


@pytest.mark.it
class TestSkillSchemaProblems:
    def test_skill_schema_problems_of_a_skill_holds_the_agent_skills_problems(self) -> None:
        #: Given
        review = b'---\nname: review\nextra: y\n---\n# Review\n'
        database = Database(_snapshot(REQUIRE_STATUS, STRING_DESCRIPTION, typing=b'', review=review))
        source = _skill_text(database, REVIEW)

        #: When
        found = database.skill_schema_problems(source)

        #: Then
        assert found == (
            SchemaProblems(
                source=AgentSkillsSchema(),
                problems=(
                    LocatedProblem(
                        problem=MissingFieldProblem('description', '`description` is required'),
                        line=LineNumber.from_int(1),
                    ),
                    LocatedProblem(
                        problem=UnknownFieldProblem(
                            'extra', '`extra` is not a field of the Agent Skills specification'
                        ),
                        line=LineNumber.from_int(3),
                    ),
                ),
            ),
        ), 'a skill is held to the Agent Skills specification alone, whatever the specifications in the repository'

    def test_skill_schema_problems_with_a_skill_with_no_frontmatter_holds_none(self) -> None:
        #: Given
        database = Database(_snapshot(REQUIRE_STATUS, STRING_DESCRIPTION, typing=b'', review=b'# Review\n'))
        source = _skill_text(database, REVIEW)

        #: When
        found = database.skill_schema_problems(source)

        #: Then
        assert found == (), 'no schema can hold a missing block: the block rules report it'

    def test_skill_schema_problems_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        review = b'---\nname: review\nextra: y\n---\n# Review\n'
        database = Database(_snapshot(REQUIRE_STATUS, STRING_DESCRIPTION, typing=b'', review=review))
        source = _skill_text(database, REVIEW)
        first = database.skill_schema_problems(source)

        #: When
        second = database.skill_schema_problems(source)

        #: Then
        assert second is first, 'a skill is held to the specification once per database, then shared by every rule'
