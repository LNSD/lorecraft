"""The database over a hand-built snapshot.

The model, each decoded text, each frontmatter, each parse tree, each token count and each skill's parse tree are
computed once, and every query about a file's content is asked with the witness its decode query returned. Opening
the database refuses a linked layout and loads the model, and the scope question reads the same snapshot. The
expanded scope behind the scope question is private to the database, so that it is built once is not observed here;
that every question after the first is answered correctly from it is.

Every snapshot here is built in memory, so no case reads the disk: the database is what wires the virtual view,
the model loader, the layout guard and the parser together.
"""

import os
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from textwrap import dedent
from typing import Final

import pytest

from lib.tree import from_tree
from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import NonZeroUnsignedInt, UnsignedInt
from lorecraft.core.path import PathComponent, RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.database import Database, DocumentText, ItemText, SkillResourceText, SkillText, Undecodable
from lorecraft.project.document import DocumentRef
from lorecraft.project.item import MarkdownItemRef
from lorecraft.project.layout import LinkedLayoutError
from lorecraft.project.skill import SkillLocation, SkillRef
from lorecraft.project.syntax import Frontmatter, Heading, LineNumber, count_tokens, split_lines
from lorecraft.project.syntax import Link as MarkdownLink
from lorecraft.project.workspace import EmptyStructureSpec, FailedStructure, LoadFailure
from lorecraft.vfs import (
    ByteOffset,
    Declaration,
    DirectoryRecord,
    EntryRecord,
    FileRecord,
    ResolvedPath,
    ScanRoot,
    Snapshot,
    SnapshotRecords,
    SymlinkRecord,
    Utf8Failure,
    Utf8Line,
    Utf8Reason,
    take_snapshot,
)

GUIDE: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('guide'))
PYTHON_GUIDE: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('python-guide'))
REVIEW: Final[SkillRef] = SkillRef(
    ResolvedPath(RootRelativePath.parse('.agents/skills')), PathComponent.parse('review')
)


def _snapshot(guide: bytes) -> Snapshot:
    """A snapshot of one `code` corpus, with a spec and a frontmatter schema, holding `guide.md`.

    Args:
        guide: Bytes of `docs/code/guide.md`, the one document in the snapshot.
    """
    return from_tree(
        {
            'docs': {
                '__meta__': {'code.md': b'# Code\n', 'code.spec.json': b'{"frontmatter": {"type": "object"}}'},
                'code': {'guide.md': guide},
            }
        }
    )


def _failed_namespace_layer_snapshot() -> Snapshot:
    """A snapshot whose `code` corpus loads and whose `code-python` namespace layer holds a structure that is not JSON.

    The one document, `docs/code/python-guide.md`, lacks the `name` the corpus's schema requires.
    """
    return from_tree(
        {
            'docs': {
                '__meta__': {
                    'code.md': b'# Code\n',
                    'code.spec.json': b'{"frontmatter": {"type": "object", "required": ["name"]}}',
                    'code-python.md': b'# Python\n',
                    'code-python.spec.json': b'not json',
                },
                'code': {'python-guide.md': b'---\ndescription: x\n---\n# Guide\n'},
            }
        }
    )


def _skill_snapshot(skill: bytes) -> Snapshot:
    """A snapshot holding one skill, `.agents/skills/review/`, whose `SKILL.md` holds `skill`.

    Args:
        skill: Bytes of the skill's `SKILL.md`.
    """
    return from_tree({'.agents': {'skills': {'review': {'SKILL.md': skill}}}})


def _document_text(database: Database, ref: DocumentRef) -> DocumentText:
    """The witness of a document the test wrote as UTF-8, as the database decodes it.

    Args:
        database: The database the document is decoded by.
        ref: A document whose bytes are UTF-8.
    """
    source = database.text(ref)
    assert isinstance(source, DocumentText), f'{ref.path} was written as UTF-8, so it decodes'
    return source


def _item_text(database: Database, ref: DocumentRef) -> ItemText:
    """The witness of a document the test wrote as UTF-8, as the database decodes it by its common reference.

    Args:
        database: The database the document is decoded by.
        ref: A document whose bytes are UTF-8.
    """
    source = database.item_text(MarkdownItemRef(ref.path))
    assert isinstance(source, ItemText), f'{ref.path} was written as UTF-8, so it decodes'
    return source


def _skill_text(database: Database, ref: SkillRef) -> SkillText:
    """The witness of a skill whose `SKILL.md` the test wrote as UTF-8, as the database decodes it.

    Args:
        database: The database the `SKILL.md` is decoded by.
        ref: A skill whose `SKILL.md` bytes are UTF-8.
    """
    source = database.skill_text(_location(database, ref))
    assert isinstance(source, SkillText), f'{ref.path} was written as UTF-8, so it decodes'
    return source


def _location(database: Database, ref: SkillRef) -> SkillLocation:
    """Where the database's model locates a skill it lists.

    Args:
        database: The database whose model lists the skill.
        ref: The skill to locate.
    """
    location = database.model().find_skill_location(ref.directory)
    assert location is not None, f'the model lists the skill {ref.directory}'
    return location


def _snapshot_of(records: Mapping[str, EntryRecord], *, scope: tuple[ScanRoot, ...] = ()) -> Snapshot:
    """A snapshot holding `records`, each keyed by its root-relative path as spelled, and `scope`.

    Args:
        records: Each record the snapshot holds, keyed by the path it was recorded at.
        scope: The scan roots the snapshot records it was taken of; none by default, as for one built by hand.
    """
    parsed: dict[RootRelativePath, EntryRecord] = {}
    for raw_path, record in records.items():
        parsed[RootRelativePath.parse(raw_path)] = record
    return Snapshot(SnapshotRecords(parsed), scope=scope)


def _climbing_chain_snapshot() -> Snapshot:
    """What `take_snapshot` records for link chains whose `..` climbs out of a directory stepped into by name.

    The tree is `climbing_chain_tree` of the filesystem tier, scanned with `skills` one level deep through its
    links and `a` one level deep. `skills/l` names `../a/tmp/../b` and leads to `a/b`; `skills/m` names `../a/b`;
    `skills/far` names `../c/tmp/../d` and leads to `c/d`; `skills/n` names `../a/missing/../b` and leads
    nowhere; `skills/out` names `../a/tmp/../../..` and climbs above the root. Every directory a followed chain
    climbs out of is recorded.
    """
    return _snapshot_of(
        {
            'a': DirectoryRecord(listed=True, climbed=True),
            'a/b': DirectoryRecord(listed=True),
            'a/b/SKILL.md': FileRecord(b'---\nname: b\n---\n'),
            'a/tmp': DirectoryRecord(listed=True, climbed=True),
            'c/d': DirectoryRecord(listed=True),
            'c/d/SKILL.md': FileRecord(b'---\nname: d\n---\n'),
            'c/tmp': DirectoryRecord(climbed=True),
            'skills': DirectoryRecord(listed=True, climbed=True),
            'skills/far': SymlinkRecord(PurePosixPath('../c/tmp/../d')),
            'skills/l': SymlinkRecord(PurePosixPath('../a/tmp/../b')),
            'skills/m': SymlinkRecord(PurePosixPath('../a/b')),
            'skills/n': SymlinkRecord(PurePosixPath('../a/missing/../b')),
            'skills/out': SymlinkRecord(PurePosixPath('../a/tmp/../../..')),
        },
        scope=(
            ScanRoot(RootRelativePath.parse('skills'), depth=UnsignedInt(1), follow_links=True),
            ScanRoot(RootRelativePath.parse('a'), depth=UnsignedInt(1)),
        ),
    )


@pytest.mark.it
class TestDatabase:
    def test_model_from_a_snapshot_lists_the_documents_the_snapshot_holds(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'---\nname: "guide"\n---\n'))

        #: When
        model = database.model()

        #: Then
        assert model.documents() == (GUIDE,), 'the model is loaded from the snapshot alone'

    def test_model_called_twice_returns_the_model_the_database_was_opened_with(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'---\nname: "guide"\n---\n'))
        first = database.model()

        #: When
        second = database.model()

        #: Then
        assert second is first, 'the model is loaded once, when the database is opened'

    def test_open_with_a_linked_docs_directory_raises_linked_layout_error(self) -> None:
        #: Given
        # What a scan records for a `docs -> documentation` link: the link on the way to the scope root, and
        # nothing behind it.
        snapshot = _snapshot_of({'docs': SymlinkRecord(PurePosixPath('documentation'))})

        #: When
        with pytest.raises(LinkedLayoutError) as exc_info:
            Database.from_snapshot(snapshot)

        #: Then
        assert exc_info.value.path == RootRelativePath.parse('docs'), 'the layout is refused before a model is loaded'

    def test_open_with_real_directories_returns_a_database(self) -> None:
        #: Given
        snapshot = _snapshot(b'---\nname: "guide"\n---\n')

        #: When
        database = Database.from_snapshot(snapshot)

        #: Then
        assert database.model().documents() == (GUIDE,), 'a snapshot of real directories is accepted'

    def test_open_with_a_structure_specification_that_states_no_rule_records_the_failure_and_raises_nothing(
        self,
    ) -> None:
        #: Given
        snapshot = from_tree(
            {'docs': {'__meta__': {'code.md': b'# Code\n', 'code.spec.json': b'{}'}, 'code': {'guide.md': b''}}}
        )
        path = RootRelativePath.parse('docs/__meta__/code.spec.json')

        #: When
        database = Database.from_snapshot(snapshot)

        #: Then
        assert database.model().load_failures == (LoadFailure(path, EmptyStructureSpec()),), (
            'the failure is a value the model records, so opening raises nothing and the database has its model'
        )
        governance = database.item_governance(MarkdownItemRef(GUIDE.path))
        assert governance is not None, 'the document is in a corpus the model holds'
        assert governance.failed_layers() == (FailedStructure(path, EmptyStructureSpec()),), (
            'the failed layer is held where its structure would be'
        )

    def test_schema_problems_with_a_failed_namespace_layer_reads_only_the_layers_that_loaded(self) -> None:
        #: Given
        database = Database.from_snapshot(_failed_namespace_layer_snapshot())
        source = _item_text(database, PYTHON_GUIDE)

        #: When
        problems = database.item_schema_problems(source)

        #: Then
        assert len(problems) == 1, 'one frontmatter schema judges the document: the failed layer states none'
        assert len(problems[0].problems) == 1, 'the corpus layer that loaded finds the required `name` missing'

    def test_outline_alignment_with_a_failed_namespace_layer_aligns_only_the_layers_that_loaded(self) -> None:
        #: Given
        database = Database.from_snapshot(_failed_namespace_layer_snapshot())
        source = _item_text(database, PYTHON_GUIDE)

        #: When
        alignments = database.item_outline_alignment(source)

        #: Then
        assert len(alignments) == 1, 'only the layer that loaded is aligned'

    def test_outline_divergences_with_a_failed_namespace_layer_finds_none_without_an_outline(self) -> None:
        #: Given
        database = Database.from_snapshot(_failed_namespace_layer_snapshot())
        source = _item_text(database, PYTHON_GUIDE)

        #: When
        divergences = database.item_outline_divergences(source)

        #: Then
        assert divergences == (), 'no outline governs the document, so nothing diverges'

    def test_is_in_scope_with_a_path_the_snapshot_scope_covers_returns_true(self) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot_of({}, scope=(ScanRoot(RootRelativePath.parse('src'), depth=UnsignedInt(0)),))
        )
        path = RootRelativePath.parse('src/tool.py')

        #: When
        in_scope = database.is_in_scope(path)

        #: Then
        assert in_scope is True, (
            'the snapshot was taken of src/, so a path in it is in scope, though the layout reads no src/'
        )

    def test_is_in_scope_with_a_path_only_the_layout_scope_covers_returns_false(self) -> None:
        #: Given
        database = Database.from_snapshot(
            _snapshot_of({}, scope=(ScanRoot(RootRelativePath.parse('src'), depth=UnsignedInt(0)),))
        )
        path = RootRelativePath.parse('docs/code/guide.md')

        #: When
        in_scope = database.is_in_scope(path)

        #: Then
        assert in_scope is False, 'the snapshot was not taken of docs/, so the layout reading it plays no part'

    def test_is_in_scope_over_a_snapshot_from_a_tree_returns_false(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'---\nname: "guide"\n---\n'))
        path = RootRelativePath.parse('docs/code/guide.md')

        #: When
        in_scope = database.is_in_scope(path)

        #: Then
        assert in_scope is False, (
            'a snapshot built from a tree scanned nothing, so even a path it holds is not in scope'
        )

    def test_is_in_scope_after_a_path_outside_the_scope_was_asked_returns_true_through_a_followed_link(self) -> None:
        #: Given
        # The skills root follows links, so the link adds skills/review to what the scan lists; the first question
        # builds the expanded scope the database keeps, and the second is answered from it.
        snapshot = _snapshot_of(
            {'.agents/skills/review': SymlinkRecord(PurePosixPath('../../skills/review'))},
            scope=(ScanRoot(RootRelativePath.parse('.agents/skills'), depth=UnsignedInt(1), follow_links=True),),
        )
        database = Database.from_snapshot(snapshot)
        database.is_in_scope(RootRelativePath.parse('src/tool.py'))
        path = RootRelativePath.parse('skills/review/absent.md')

        #: When
        in_scope = database.is_in_scope(path)

        #: Then
        assert in_scope is True, 'every question after the first is answered from the same expanded scan roots'

    def test_find_file_through_a_link_climbing_out_of_a_directory_stepped_into_returns_the_resolved_file(
        self,
    ) -> None:
        #: Given
        database = Database.from_snapshot(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/l/SKILL.md')

        #: When
        resolved = database.find_file(path)

        #: Then
        assert resolved == RootRelativePath.parse('a/b/SKILL.md'), 'the `..` after a/tmp is a, so skills/l is a/b'

    def test_find_file_through_a_link_climbing_out_of_an_unlisted_directory_returns_the_resolved_file(
        self,
    ) -> None:
        #: Given
        database = Database.from_snapshot(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/far/SKILL.md')

        #: When
        resolved = database.find_file(path)

        #: Then
        assert resolved == RootRelativePath.parse('c/d/SKILL.md'), (
            'no listing shows c/tmp, but the recorded climb out of it does'
        )

    def test_find_file_through_a_link_climbing_out_of_a_missing_directory_returns_none(self) -> None:
        #: Given
        database = Database.from_snapshot(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/n/SKILL.md')

        #: When
        resolved = database.find_file(path)

        #: Then
        assert resolved is None, 'a/missing does not exist, so skills/n leads to no file, though a/b/SKILL.md does'

    def test_is_in_scope_through_a_link_climbing_out_of_a_missing_directory_returns_false(self) -> None:
        #: Given
        database = Database.from_snapshot(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/n/SKILL.md')

        #: When
        in_scope = database.is_in_scope(path)

        #: Then
        assert in_scope is False, 'the scan never climbed out of a/missing, so the scope query does not either'

    def test_find_file_through_a_followed_link_returns_the_resolved_file(self) -> None:
        #: Given
        database = Database.from_snapshot(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/m/SKILL.md')

        #: When
        resolved = database.find_file(path)

        #: Then
        assert resolved == RootRelativePath.parse('a/b/SKILL.md'), 'the scan follows skills/m to a/b'

    def test_text_of_a_utf8_document_returns_its_witness(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'---\nname: "guide"\n---\n'))

        #: When
        source = database.text(GUIDE)

        #: Then
        assert source == DocumentText(GUIDE, '---\nname: "guide"\n---\n'), 'the witness holds the ref and its text'

    def test_text_of_a_document_that_is_not_utf8_returns_undecodable(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'---\nname: "gu\xffide"\n---\n'))

        #: When
        source = database.text(GUIDE)

        #: Then
        failure = Utf8Failure(
            line=Utf8Line(2),
            offset=ByteOffset(13),
            invalid=b'\xff',
            reason=Utf8Reason.INVALID_START_BYTE,
        )
        assert source == Undecodable(GUIDE, failure), (
            'a decode failure is an answer naming the document and where its bytes stop being UTF-8, not an error'
        )

    def test_text_of_a_document_that_is_not_utf8_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'---\nname: "gu\xffide"\n---\n'))
        first = database.text(GUIDE)

        #: When
        second = database.text(GUIDE)

        #: Then
        assert second is first, 'an undecodable document is cached like any answer, so it is decoded once'

    def test_source_lines_of_a_listed_document_returns_its_lines_numbered_as_the_rules_number_them(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'one\r\ntwo\x0cstill two\n'))

        #: When
        lines = database.source_lines(GUIDE.path)

        #: Then
        assert lines == ('one', 'two\x0cstill two'), f'only a newline ends a line, got {lines}'

    def test_source_lines_of_a_document_opening_with_a_byte_order_mark_returns_the_lines_of_its_decoded_text(
        self,
    ) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'\xef\xbb\xbf# Guide\nBody\n'))
        decoded = _document_text(database, GUIDE)

        #: When
        lines = database.source_lines(GUIDE.path)

        #: Then
        assert lines == split_lines(decoded.text), f'the excerpt is cut from the decoded text, got {lines}'
        assert lines == ('\ufeff# Guide', 'Body'), f'the mark stays in the text the rules numbered, got {lines}'

    def test_source_lines_of_a_skill_returns_the_lines_of_its_decoded_text(self) -> None:
        #: Given
        database = Database.from_snapshot(_skill_snapshot(b'\xef\xbb\xbf---\nname: review\n---\nBody\n'))
        decoded = _skill_text(database, REVIEW)

        #: When
        lines = database.source_lines(REVIEW.path)

        #: Then
        assert lines == split_lines(decoded.text), f'the excerpt is cut from the decoded text, got {lines}'

    def test_source_lines_of_a_skill_resource_returns_the_lines_of_its_decoded_text(self) -> None:
        #: Given
        snapshot = from_tree(
            {'.agents': {'skills': {'review': {'SKILL.md': b'# Review\n', 'guide.md': b'\xef\xbb\xbfone\ntwo\n'}}}}
        )
        database = Database.from_snapshot(snapshot)
        location = database.model().skill_locations[REVIEW]
        resource = database.skill_resources(location).resources[0]
        decoded = database.skill_resource_text(resource)
        assert isinstance(decoded, SkillResourceText), 'the resource was written as UTF-8, so it decodes'

        #: When
        lines = database.source_lines(resource.ref.path)

        #: Then
        assert lines == split_lines(decoded.text), f'the excerpt is cut from the decoded text, got {lines}'

    def test_source_lines_of_a_specification_returns_its_lines(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'# Guide\n'))
        path = RootRelativePath.parse('docs/__meta__/code.md')

        #: When
        lines = database.source_lines(path)

        #: Then
        assert lines == ('# Code',), f'a file that is no document can be excerpted too, got {lines}'

    def test_source_lines_of_a_file_that_is_not_utf8_returns_none(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'\xff\xfe\n'))

        #: When
        lines = database.source_lines(GUIDE.path)

        #: Then
        assert lines is None, f'a file that does not decode has nothing to excerpt, got {lines}'

    def test_source_lines_of_a_path_no_decode_query_owns_returns_none(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'# Guide\n'))
        path = RootRelativePath.parse('docs/code/missing.md')

        #: When
        lines = database.source_lines(path)

        #: Then
        assert lines is None, f'a path that is no listed file has nothing to excerpt, got {lines}'

    def test_source_lines_of_a_specification_the_snapshot_does_not_hold_returns_none(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'# Guide\n'))
        path = RootRelativePath.parse('docs/__meta__/missing.spec.json')

        #: When
        lines = database.source_lines(path)

        #: Then
        assert lines is None, f'a missing specification has nothing to excerpt, got {lines}'

    @pytest.mark.skipif(os.geteuid() == 0, reason='root ignores file and directory permissions')
    def test_source_lines_of_a_resource_of_a_skill_that_cannot_be_listed_returns_none(
        self, tmp_path: Path, lock: Callable[[Path], None]
    ) -> None:
        #: Given
        skill = tmp_path / '.agents' / 'skills' / 'review'
        (skill / 'references').mkdir(parents=True)
        (skill / 'SKILL.md').write_text('# Review\n', encoding='utf-8')
        (skill / 'guide.md').write_text('# Guide\n', encoding='utf-8')
        # The walk over the skill's resources enters `references`, which the scan then records as refused.
        lock(skill / 'references')
        scope = (ScanRoot(RootRelativePath.parse('.agents/skills'), depth=None, follow_links=True),)
        database = Database.from_snapshot(
            take_snapshot(tmp_path, scope, declaration=Declaration(is_file=lambda _: False))
        )
        path = RootRelativePath.parse('.agents/skills/review/guide.md')

        #: When
        lines = database.source_lines(path)

        #: Then
        assert lines is None, f'a skill whose resources cannot be listed has nothing to excerpt, got {lines}'

    def test_frontmatter_of_a_listed_document_returns_its_decoded_block(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'---\nname: "guide"\n---\n'))
        source = _document_text(database, GUIDE)

        #: When
        frontmatter = database.frontmatter(source)

        #: Then
        assert isinstance(frontmatter, Frontmatter), 'the snapshot bytes decode into a frontmatter node'
        assert frontmatter.data == FrozenMapping({'name': 'guide'}), 'the frontmatter holds the snapshot content'

    def test_frontmatter_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'---\nname: "guide"\n---\n'))
        source = _document_text(database, GUIDE)
        first = database.frontmatter(source)

        #: When
        second = database.frontmatter(source)

        #: Then
        assert second is first, 'a document frontmatter is decoded once per database, then shared by every check'

    def test_parse_of_a_listed_document_returns_its_headings(self) -> None:
        #: Given
        text = dedent(
            """\
            ---
            name: "guide"
            ---
            # Guide
            """
        )
        database = Database.from_snapshot(_snapshot(text.encode()))
        source = _document_text(database, GUIDE)

        #: When
        document = database.parse(source)

        #: Then
        assert document.headings == (
            Heading(level=1, text='Guide', line=LineNumber(NonZeroUnsignedInt(4)), empty=True, words=UnsignedInt(0)),
        ), 'the parse tree holds the snapshot content'

    def test_source_lines_of_a_file_with_lone_carriage_returns_holds_the_line_a_heading_is_reported_on(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'one\r\r# Guide\r\rtwo\r'))
        source = _document_text(database, GUIDE)

        #: When
        lines = database.source_lines(GUIDE.path)
        document = database.parse(source)

        #: Then
        assert lines is not None, 'a document that decodes has lines to excerpt'
        heading_line = document.headings[0].line.value
        assert lines[heading_line - 1] == '# Guide', (
            f'the excerpted line a heading number names is the heading, got {lines!r} for line {heading_line}'
        )

    def test_parse_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database.from_snapshot(_snapshot(b'---\nname: "guide"\n---\n'))
        source = _document_text(database, GUIDE)
        first = database.parse(source)

        #: When
        second = database.parse(source)

        #: Then
        assert second is first, 'a document is parsed once per database, then shared by every check'

    def test_token_count_of_a_listed_document_counts_its_whole_file(self) -> None:
        #: Given
        # no prose words at all, but an agent loading the file still pays for every character of it
        guide = '---\nname: "guide"\n---\n```python\nx = 1\n```\n'
        database = Database.from_snapshot(_snapshot(guide.encode()))
        source = _document_text(database, GUIDE)
        expected = count_tokens(guide)

        #: When
        tokens = database.token_count(source)

        #: Then
        assert tokens == expected, f'frontmatter and code count too, got {tokens}'

    def test_document_line_count_of_a_listed_document_counts_its_whole_file(self) -> None:
        #: Given
        # three lines of frontmatter and two of body, the last one ending in a newline
        database = Database.from_snapshot(_snapshot(b'---\nname: "guide"\n---\n# Guide\n\n'))
        source = _document_text(database, GUIDE)

        #: When
        lines = database.document_line_count(source)

        #: Then
        assert lines == UnsignedInt(5), f'the frontmatter counts too, and the final newline adds no line, got {lines}'

    def test_skill_text_of_a_utf8_skill_returns_its_witness(self) -> None:
        #: Given
        database = Database.from_snapshot(_skill_snapshot(b'---\nname: review\n---\n'))
        location = _location(database, REVIEW)

        #: When
        source = database.skill_text(location)

        #: Then
        assert source == SkillText(_location(database, REVIEW), '---\nname: review\n---\n'), (
            'the witness holds the model-issued location and the text'
        )

    def test_skill_text_of_a_skill_that_is_not_utf8_returns_undecodable(self) -> None:
        #: Given
        database = Database.from_snapshot(_skill_snapshot(b'---\nname: caf\xe9\n---\n'))
        location = _location(database, REVIEW)

        #: When
        source = database.skill_text(location)

        #: Then
        failure = Utf8Failure(
            line=Utf8Line(2),
            offset=ByteOffset(13),
            invalid=b'\xe9',
            reason=Utf8Reason.INVALID_CONTINUATION_BYTE,
        )
        assert source == Undecodable(REVIEW, failure), (
            'a decode failure is an answer naming the skill and where its bytes stop being UTF-8, not an error'
        )

    def test_skill_text_of_a_skill_that_is_not_utf8_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database.from_snapshot(_skill_snapshot(b'---\nname: caf\xe9\n---\n'))
        first = database.skill_text(_location(database, REVIEW))
        location = _location(database, REVIEW)

        #: When
        second = database.skill_text(location)

        #: Then
        assert second is first, 'an undecodable skill is cached like any answer, so it is decoded once'

    def test_skill_parse_of_a_skill_returns_its_links(self) -> None:
        #: Given
        database = Database.from_snapshot(
            _skill_snapshot(b'---\nname: review\n---\n# Review\n\nSee [the guide](guide.md).\n')
        )
        source = _skill_text(database, REVIEW)

        #: When
        document = database.skill_parse(source)

        #: Then
        assert document.links == (MarkdownLink(url='guide.md', line=LineNumber(NonZeroUnsignedInt(6))),), (
            'the SKILL.md bytes parse into a tree holding its links'
        )

    def test_skill_parse_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database.from_snapshot(_skill_snapshot(b'---\nname: review\n---\n# Review\n'))
        source = _skill_text(database, REVIEW)
        first = database.skill_parse(source)

        #: When
        second = database.skill_parse(source)

        #: Then
        assert second is first, 'a skill is parsed once per database, then shared by every check'

    def test_skill_parse_of_a_linked_skill_parses_the_skill_the_link_leads_to(self) -> None:
        #: Given
        # What a scan records for `.agents/skills/review -> ../../skills/review`: the link in the skills directory,
        # and the SKILL.md at the resolved path it leads to, and the directories on the way, listed so the model
        # lists the skill and climbed by the link's `..`.
        shipped = from_tree({'skills': {'review': {'SKILL.md': b'---\nname: review\n---\n[the guide](guide.md)\n'}}})
        records: dict[RootRelativePath, EntryRecord] = dict(shipped.records)
        records[RootRelativePath.parse('.agents')] = DirectoryRecord(listed=True, climbed=True)
        records[RootRelativePath.parse('.agents/skills')] = DirectoryRecord(listed=True, climbed=True)
        records[RootRelativePath.parse('.agents/skills/review')] = SymlinkRecord(PurePosixPath('../../skills/review'))
        database = Database.from_snapshot(Snapshot(SnapshotRecords(records)))
        source = _skill_text(database, REVIEW)

        #: When
        document = database.skill_parse(source)

        #: Then
        assert document.links == (MarkdownLink(url='guide.md', line=LineNumber(NonZeroUnsignedInt(4))),), (
            'the ref names the linked entry, and the tree is parsed from the SKILL.md the link leads to'
        )

    def test_skill_line_count_of_a_skill_counts_its_whole_file(self) -> None:
        #: Given
        # three lines of frontmatter and three of body, the last one ending in a newline
        database = Database.from_snapshot(
            _skill_snapshot(b'---\nname: review\n---\n# Review\n\nSee [the guide](guide.md).\n')
        )
        source = _skill_text(database, REVIEW)

        #: When
        lines = database.skill_line_count(source)

        #: Then
        assert lines == UnsignedInt(6), f'the frontmatter counts too, and the final newline adds no line, got {lines}'

    def test_skill_frontmatter_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database.from_snapshot(_skill_snapshot(b'---\nname: review\n---\n'))
        source = _skill_text(database, REVIEW)
        first = database.skill_frontmatter(source)

        #: When
        second = database.skill_frontmatter(source)

        #: Then
        assert isinstance(first, Frontmatter), 'the skill bytes decode into a frontmatter node'
        assert second is first, 'a skill frontmatter is decoded once per database, then shared by every check'
