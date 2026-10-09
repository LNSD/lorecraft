"""The database over a hand-built snapshot.

The model, each decoded text, each frontmatter, each parse tree, each token count and each skill's parse tree are
computed once, and every query about a file's content is asked with the witness its decode query returned. The layout
guard and the scope question read the same snapshot. The expanded scope behind the scope question is
private to the database, so that it is built once is not observed here; that every question after the first is
answered correctly from it is.

Every snapshot here is built in memory, so no case reads the disk: the database is what wires the virtual view,
the model loader, the layout guard and the parser together.
"""

from collections.abc import Mapping
from pathlib import PurePosixPath
from textwrap import dedent
from typing import Final

import pytest

from lorecraft.core.mapping import FrozenMapping
from lorecraft.core.num import UnsignedInt
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.database import Database, DocumentText, SkillText, Undecodable
from lorecraft.project.document import DocumentRef
from lorecraft.project.layout import LinkedLayoutError
from lorecraft.project.skill import SkillRef
from lorecraft.project.syntax import Frontmatter, Heading, LineNumber, count_tokens
from lorecraft.project.syntax import Link as MarkdownLink
from lorecraft.vfs import (
    DirectoryRecord,
    EntryRecord,
    FileRecord,
    ScanRoot,
    Snapshot,
    SymlinkRecord,
    Utf8Failure,
    Utf8Reason,
)

GUIDE: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('guide'))
REVIEW: Final[SkillRef] = SkillRef(RootRelativePath.parse('.agents/skills/review'))


def _snapshot(guide: bytes) -> Snapshot:
    """A snapshot of one `code` corpus, with a spec and a frontmatter schema, holding `guide.md`.

    Args:
        guide: Bytes of `docs/code/guide.md`, the one document in the snapshot.
    """
    return Snapshot.from_tree(
        {
            'docs': {
                '__meta__': {'code.md': b'# Code\n', 'code.structure.json': b'{"frontmatter": {"type": "object"}}'},
                'code': {'guide.md': guide},
            }
        }
    )


def _skill_snapshot(skill: bytes) -> Snapshot:
    """A snapshot holding one skill, `.agents/skills/review/`, whose `SKILL.md` holds `skill`.

    Args:
        skill: Bytes of the skill's `SKILL.md`.
    """
    return Snapshot.from_tree({'.agents': {'skills': {'review': {'SKILL.md': skill}}}})


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


def _snapshot_of(records: Mapping[str, EntryRecord], *, scope: tuple[ScanRoot, ...] = ()) -> Snapshot:
    """A snapshot holding `records`, each keyed by its root-relative path as spelled, and `scope`.

    Args:
        records: Each record the snapshot holds, keyed by the path it was recorded at.
        scope: The scan roots the snapshot records it was taken of; none by default, as for one built by hand.
    """
    parsed: dict[RootRelativePath, EntryRecord] = {}
    for raw_path, record in records.items():
        parsed[RootRelativePath.parse(raw_path)] = record
    return Snapshot(FrozenMapping(parsed), scope=scope)


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
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))

        #: When
        model = database.model()

        #: Then
        assert model.documents() == (GUIDE,), 'the model is loaded from the snapshot alone'

    def test_model_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))
        first = database.model()

        #: When
        second = database.model()

        #: Then
        assert second is first, 'the model is loaded once per database, then cached'

    def test_reject_linked_layout_with_a_linked_docs_directory_raises_linked_layout_error(self) -> None:
        #: Given
        # What a scan records for a `docs -> documentation` link: the link on the way to the scope root, and
        # nothing behind it.
        database = Database(_snapshot_of({'docs': SymlinkRecord(PurePosixPath('documentation'))}))

        #: When
        with pytest.raises(LinkedLayoutError) as exc_info:
            database.reject_linked_layout()

        #: Then
        assert exc_info.value.path == RootRelativePath.parse('docs'), 'the guard reads the snapshot the database holds'

    def test_reject_linked_layout_with_real_directories_returns_without_raising(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))

        #: When
        outcome = database.reject_linked_layout()

        #: Then
        assert outcome is None, 'a snapshot of real directories is accepted'

    def test_is_in_scope_with_a_path_the_snapshot_scope_covers_returns_true(self) -> None:
        #: Given
        database = Database(_snapshot_of({}, scope=(ScanRoot(RootRelativePath.parse('src'), depth=UnsignedInt(0)),)))

        #: When
        in_scope = database.is_in_scope(RootRelativePath.parse('src/tool.py'))

        #: Then
        assert in_scope is True, (
            'the snapshot was taken of src/, so a path in it is in scope, though the layout reads no src/'
        )

    def test_is_in_scope_with_a_path_only_the_layout_scope_covers_returns_false(self) -> None:
        #: Given
        database = Database(_snapshot_of({}, scope=(ScanRoot(RootRelativePath.parse('src'), depth=UnsignedInt(0)),)))

        #: When
        in_scope = database.is_in_scope(RootRelativePath.parse('docs/code/guide.md'))

        #: Then
        assert in_scope is False, 'the snapshot was not taken of docs/, so the layout reading it plays no part'

    def test_is_in_scope_over_a_snapshot_from_a_tree_returns_false(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))

        #: When
        in_scope = database.is_in_scope(RootRelativePath.parse('docs/code/guide.md'))

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
        database = Database(snapshot)
        database.is_in_scope(RootRelativePath.parse('src/tool.py'))

        #: When
        in_scope = database.is_in_scope(RootRelativePath.parse('skills/review/absent.md'))

        #: Then
        assert in_scope is True, 'every question after the first is answered from the same expanded scan roots'

    def test_find_file_through_a_link_climbing_out_of_a_directory_stepped_into_returns_the_resolved_file(
        self,
    ) -> None:
        #: Given
        database = Database(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/l/SKILL.md')

        #: When
        resolved = database.find_file(path)

        #: Then
        assert resolved == RootRelativePath.parse('a/b/SKILL.md'), 'the `..` after a/tmp is a, so skills/l is a/b'

    def test_find_file_through_a_link_climbing_out_of_an_unlisted_directory_returns_the_resolved_file(
        self,
    ) -> None:
        #: Given
        database = Database(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/far/SKILL.md')

        #: When
        resolved = database.find_file(path)

        #: Then
        assert resolved == RootRelativePath.parse('c/d/SKILL.md'), (
            'no listing shows c/tmp, but the recorded climb out of it does'
        )

    def test_find_file_through_a_link_climbing_out_of_a_missing_directory_returns_none(self) -> None:
        #: Given
        database = Database(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/n/SKILL.md')

        #: When
        resolved = database.find_file(path)

        #: Then
        assert resolved is None, 'a/missing does not exist, so skills/n leads to no file, though a/b/SKILL.md does'

    def test_is_in_scope_through_a_link_climbing_out_of_a_missing_directory_returns_false(self) -> None:
        #: Given
        database = Database(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/n/SKILL.md')

        #: When
        in_scope = database.is_in_scope(path)

        #: Then
        assert in_scope is False, 'the scan never climbed out of a/missing, so the scope query does not either'

    def test_find_file_through_a_followed_link_returns_the_resolved_file(self) -> None:
        #: Given
        database = Database(_climbing_chain_snapshot())
        path = RootRelativePath.parse('skills/m/SKILL.md')

        #: When
        resolved = database.find_file(path)

        #: Then
        assert resolved == RootRelativePath.parse('a/b/SKILL.md'), 'the scan follows skills/m to a/b'

    def test_text_of_a_utf8_document_returns_its_witness(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))

        #: When
        source = database.text(GUIDE)

        #: Then
        assert source == DocumentText(GUIDE, '---\nname: "guide"\n---\n'), 'the witness holds the ref and its text'

    def test_text_of_a_document_that_is_not_utf8_returns_undecodable(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "gu\xffide"\n---\n'))

        #: When
        source = database.text(GUIDE)

        #: Then
        failure = Utf8Failure(
            line=2,
            offset=13,
            invalid=b'\xff',
            reason=Utf8Reason.INVALID_START_BYTE,
        )
        assert source == Undecodable(GUIDE, failure), (
            'a decode failure is an answer naming the document and where its bytes stop being UTF-8, not an error'
        )

    def test_text_of_a_document_that_is_not_utf8_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "gu\xffide"\n---\n'))
        first = database.text(GUIDE)

        #: When
        second = database.text(GUIDE)

        #: Then
        assert second is first, 'an undecodable document is cached like any answer, so it is decoded once'

    def test_source_lines_of_a_listed_document_returns_its_lines_numbered_as_the_rules_number_them(self) -> None:
        #: Given
        database = Database(_snapshot(b'one\r\ntwo\x0cstill two\n'))

        #: When
        lines = database.source_lines(GUIDE.path)

        #: Then
        assert lines == ('one', 'two\x0cstill two'), f'only a newline ends a line, got {lines}'

    def test_source_lines_of_a_file_opening_with_a_byte_order_mark_drops_the_mark(self) -> None:
        #: Given
        database = Database(_snapshot(b'\xef\xbb\xbf# Guide\nBody\n'))

        #: When
        lines = database.source_lines(GUIDE.path)

        #: Then
        assert lines == ('# Guide', 'Body'), f'the mark is no character of the first line, got {lines}'

    def test_source_lines_of_a_specification_returns_its_lines(self) -> None:
        #: Given
        database = Database(_snapshot(b'# Guide\n'))

        #: When
        lines = database.source_lines(RootRelativePath.parse('docs/__meta__/code.md'))

        #: Then
        assert lines == ('# Code',), f'a file that is no document can be excerpted too, got {lines}'

    def test_source_lines_of_a_file_that_is_not_utf8_returns_none(self) -> None:
        #: Given
        database = Database(_snapshot(b'\xff\xfe\n'))

        #: When
        lines = database.source_lines(GUIDE.path)

        #: Then
        assert lines is None, f'a file that does not decode has nothing to excerpt, got {lines}'

    def test_source_lines_of_a_path_the_snapshot_does_not_hold_returns_none(self) -> None:
        #: Given
        database = Database(_snapshot(b'# Guide\n'))

        #: When
        lines = database.source_lines(RootRelativePath.parse('docs/code/missing.md'))

        #: Then
        assert lines is None, f'a missing file has nothing to excerpt, got {lines}'

    def test_frontmatter_of_a_listed_document_returns_its_decoded_block(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))
        source = _document_text(database, GUIDE)

        #: When
        frontmatter = database.frontmatter(source)

        #: Then
        assert isinstance(frontmatter, Frontmatter), 'the snapshot bytes decode into a frontmatter node'
        assert frontmatter.data == FrozenMapping({'name': 'guide'}), 'the frontmatter holds the snapshot content'

    def test_frontmatter_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))
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
        database = Database(_snapshot(text.encode()))
        source = _document_text(database, GUIDE)

        #: When
        document = database.parse(source)

        #: Then
        assert document.headings == (
            Heading(level=1, text='Guide', line=LineNumber.from_int(4), empty=True, words=0),
        ), 'the parse tree holds the snapshot content'

    def test_parse_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))
        source = _document_text(database, GUIDE)
        first = database.parse(source)

        #: When
        second = database.parse(source)

        #: Then
        assert second is first, 'a document is parsed once per database, then shared by every check'

    def test_tokens_of_a_listed_document_counts_its_whole_file(self) -> None:
        #: Given
        # no prose words at all, but an agent loading the file still pays for every character of it
        guide = '---\nname: "guide"\n---\n```python\nx = 1\n```\n'
        database = Database(_snapshot(guide.encode()))
        source = _document_text(database, GUIDE)
        expected = count_tokens(guide)

        #: When
        tokens = database.tokens(source)

        #: Then
        assert tokens == expected, f'frontmatter and code count too, got {tokens}'

    def test_document_lines_of_a_listed_document_counts_its_whole_file(self) -> None:
        #: Given
        # three lines of frontmatter and two of body, the last one ending in a newline
        database = Database(_snapshot(b'---\nname: "guide"\n---\n# Guide\n\n'))
        source = _document_text(database, GUIDE)

        #: When
        lines = database.document_lines(source)

        #: Then
        assert lines == 5, f'the frontmatter counts too, and the final newline adds no line, got {lines}'

    def test_skill_text_of_a_utf8_skill_returns_its_witness(self) -> None:
        #: Given
        database = Database(_skill_snapshot(b'---\nname: review\n---\n'))

        #: When
        source = database.skill_text(REVIEW)

        #: Then
        assert source == SkillText(REVIEW, '---\nname: review\n---\n'), 'the witness holds the ref and its text'

    def test_skill_text_of_a_skill_that_is_not_utf8_returns_undecodable(self) -> None:
        #: Given
        database = Database(_skill_snapshot(b'---\nname: caf\xe9\n---\n'))

        #: When
        source = database.skill_text(REVIEW)

        #: Then
        failure = Utf8Failure(
            line=2,
            offset=13,
            invalid=b'\xe9',
            reason=Utf8Reason.INVALID_CONTINUATION_BYTE,
        )
        assert source == Undecodable(REVIEW, failure), (
            'a decode failure is an answer naming the skill and where its bytes stop being UTF-8, not an error'
        )

    def test_skill_text_of_a_skill_that_is_not_utf8_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database(_skill_snapshot(b'---\nname: caf\xe9\n---\n'))
        first = database.skill_text(REVIEW)

        #: When
        second = database.skill_text(REVIEW)

        #: Then
        assert second is first, 'an undecodable skill is cached like any answer, so it is decoded once'

    def test_skill_parse_of_a_skill_returns_its_links(self) -> None:
        #: Given
        database = Database(_skill_snapshot(b'---\nname: review\n---\n# Review\n\nSee [the guide](guide.md).\n'))
        source = _skill_text(database, REVIEW)

        #: When
        document = database.skill_parse(source)

        #: Then
        assert document.links == (MarkdownLink(url='guide.md', line=LineNumber.from_int(6)),), (
            'the SKILL.md bytes parse into a tree holding its links'
        )

    def test_skill_parse_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database(_skill_snapshot(b'---\nname: review\n---\n# Review\n'))
        source = _skill_text(database, REVIEW)
        first = database.skill_parse(source)

        #: When
        second = database.skill_parse(source)

        #: Then
        assert second is first, 'a skill is parsed once per database, then shared by every check'

    def test_skill_parse_of_a_linked_skill_parses_the_skill_the_link_leads_to(self) -> None:
        #: Given
        # What a scan records for `.agents/skills/review -> ../../skills/review`: the link in the skills directory,
        # and the SKILL.md at the resolved path it leads to.
        shipped = Snapshot.from_tree(
            {'skills': {'review': {'SKILL.md': b'---\nname: review\n---\n[the guide](guide.md)\n'}}}
        )
        records: dict[RootRelativePath, EntryRecord] = dict(shipped.records)
        records[RootRelativePath.parse('.agents/skills/review')] = SymlinkRecord(PurePosixPath('../../skills/review'))
        database = Database(Snapshot(FrozenMapping(records)))
        source = _skill_text(database, REVIEW)

        #: When
        document = database.skill_parse(source)

        #: Then
        assert document.links == (MarkdownLink(url='guide.md', line=LineNumber.from_int(4)),), (
            'the ref names the linked entry, and the tree is parsed from the SKILL.md the link leads to'
        )

    def test_skill_lines_of_a_skill_counts_its_whole_file(self) -> None:
        #: Given
        # three lines of frontmatter and three of body, the last one ending in a newline
        database = Database(_skill_snapshot(b'---\nname: review\n---\n# Review\n\nSee [the guide](guide.md).\n'))
        source = _skill_text(database, REVIEW)

        #: When
        lines = database.skill_lines(source)

        #: Then
        assert lines == 6, f'the frontmatter counts too, and the final newline adds no line, got {lines}'

    def test_skill_frontmatter_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database(_skill_snapshot(b'---\nname: review\n---\n'))
        source = _skill_text(database, REVIEW)
        first = database.skill_frontmatter(source)

        #: When
        second = database.skill_frontmatter(source)

        #: Then
        assert isinstance(first, Frontmatter), 'the skill bytes decode into a frontmatter node'
        assert second is first, 'a skill frontmatter is decoded once per database, then shared by every check'
