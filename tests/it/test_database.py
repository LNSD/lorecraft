"""The database over a hand-built snapshot.

The model, each frontmatter, each parse tree, each token count and each skill's parse tree are computed once, and
the layout guard and the scope question read the same snapshot. The expanded scope behind the scope question is
private to the database, so that it is built once is not observed here; that every question after the first is
answered correctly from it is.

Every snapshot here is built in memory, so no case reads the disk: the database is what wires the virtual view,
the model loader, the layout guard and the parser together.
"""

from pathlib import PurePosixPath
from typing import Final

import pytest

from lorecraft.checks import Database
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentDecodeError, DocumentRef
from lorecraft.project.layout import LinkedLayoutError
from lorecraft.project.skill import SkillDecodeError, SkillRef
from lorecraft.project.syntax import Frontmatter, LineNumber, count_tokens
from lorecraft.project.syntax import Link as MarkdownLink
from lorecraft.vfs import DirEntry, EntryKind, FileBytes, Link, Listing, ScanRoot, Snapshot

GUIDE: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('guide'))
REVIEW: Final[SkillRef] = SkillRef(RootRelativePath.parse('.agents/skills/review'))


def _snapshot(guide: bytes) -> Snapshot:
    """A snapshot of one `code` corpus, with a spec and a frontmatter schema, holding `guide.md`.

    Args:
        guide: Bytes of `docs/code/guide.md`, the one document in the snapshot.
    """
    return Snapshot.from_files(
        {
            RootRelativePath.parse('docs/__meta__/code.md'): b'# Code\n',
            RootRelativePath.parse('docs/__meta__/code.structure.json'): b'{"frontmatter": {"type": "object"}}',
            RootRelativePath.parse('docs/code/guide.md'): guide,
        }
    )


def _skill_snapshot(skill: bytes) -> Snapshot:
    """A snapshot holding one skill, `.agents/skills/review/`, whose `SKILL.md` holds `skill`.

    Args:
        skill: Bytes of the skill's `SKILL.md`.
    """
    return Snapshot.from_files({RootRelativePath.parse('.agents/skills/review/SKILL.md'): skill})


def _refused_chain_snapshot() -> Snapshot:
    """What `take_snapshot` records for a link chain the scan refuses, whose target another root lists anyway.

    The tree is `refused_chain_tree` of the filesystem tier, scanned with `skills` one level deep through its
    links and `a` one level deep. `skills/l` names `../a/tmp/../b`, whose `..` climbs out of `a/tmp`, a
    directory stepped into by name since the link, so the scan does not follow it; `skills/m` names `../a/b`
    and is followed. The root `a` lists `a/b` either way.
    """
    return Snapshot(
        listings=(
            Listing(
                RootRelativePath.parse('a'), (DirEntry('b', EntryKind.DIRECTORY), DirEntry('tmp', EntryKind.DIRECTORY))
            ),
            Listing(RootRelativePath.parse('a/b'), (DirEntry('SKILL.md', EntryKind.FILE),)),
            Listing(RootRelativePath.parse('a/tmp'), ()),
            Listing(
                RootRelativePath.parse('skills'), (DirEntry('l', EntryKind.SYMLINK), DirEntry('m', EntryKind.SYMLINK))
            ),
        ),
        files=(FileBytes(RootRelativePath.parse('a/b/SKILL.md'), b'---\nname: b\n---\n'),),
        links=(
            Link(RootRelativePath.parse('skills/l'), PurePosixPath('../a/tmp/../b')),
            Link(RootRelativePath.parse('skills/m'), PurePosixPath('../a/b')),
        ),
        scope=(
            ScanRoot(RootRelativePath.parse('skills'), depth=1, follow_links=True),
            ScanRoot(RootRelativePath.parse('a'), depth=1),
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

    def test_require_real_layout_with_a_linked_docs_directory_raises_linked_layout_error(self) -> None:
        #: Given
        # What a scan records for a `docs -> documentation` link: the link on the way to the scope root, and
        # nothing behind it.
        snapshot = Snapshot(
            listings=(),
            files=(),
            links=(Link(RootRelativePath.parse('docs'), PurePosixPath('documentation')),),
        )
        database = Database(snapshot)

        #: When
        with pytest.raises(LinkedLayoutError) as exc_info:
            database.require_real_layout()

        #: Then
        assert exc_info.value.path == RootRelativePath.parse('docs'), 'the guard reads the snapshot the database holds'

    def test_require_real_layout_with_real_directories_returns_without_raising(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))

        #: When
        outcome = database.require_real_layout()

        #: Then
        assert outcome is None, 'a snapshot of real directories is accepted'

    def test_is_in_scope_with_a_path_the_snapshot_scope_covers_returns_true(self) -> None:
        #: Given
        snapshot = Snapshot(listings=(), files=(), scope=(ScanRoot(RootRelativePath.parse('src'), depth=0),))
        database = Database(snapshot)

        #: When
        in_scope = database.is_in_scope(RootRelativePath.parse('src/tool.py'))

        #: Then
        assert in_scope is True, (
            'the snapshot was taken of src/, so a path in it is in scope, though the layout reads no src/'
        )

    def test_is_in_scope_with_a_path_only_the_layout_scope_covers_returns_false(self) -> None:
        #: Given
        snapshot = Snapshot(listings=(), files=(), scope=(ScanRoot(RootRelativePath.parse('src'), depth=0),))
        database = Database(snapshot)

        #: When
        in_scope = database.is_in_scope(RootRelativePath.parse('docs/code/guide.md'))

        #: Then
        assert in_scope is False, 'the snapshot was not taken of docs/, so the layout reading it plays no part'

    def test_is_in_scope_over_a_snapshot_from_files_returns_false(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))

        #: When
        in_scope = database.is_in_scope(RootRelativePath.parse('docs/code/guide.md'))

        #: Then
        assert in_scope is False, 'a snapshot built from files scanned nothing, so even a path it holds is not in scope'

    def test_is_in_scope_after_a_path_outside_the_scope_was_asked_returns_true_through_a_followed_link(self) -> None:
        #: Given
        # The skills root follows links, so the link adds skills/review to what the scan lists; the first question
        # builds the expanded scope the database keeps, and the second is answered from it.
        snapshot = Snapshot(
            listings=(),
            files=(),
            links=(Link(RootRelativePath.parse('.agents/skills/review'), PurePosixPath('../../skills/review')),),
            scope=(ScanRoot(RootRelativePath.parse('.agents/skills'), depth=1, follow_links=True),),
        )
        database = Database(snapshot)
        database.is_in_scope(RootRelativePath.parse('src/tool.py'))

        #: When
        in_scope = database.is_in_scope(RootRelativePath.parse('skills/review/absent.md'))

        #: Then
        assert in_scope is True, 'every question after the first is answered from the same expanded scan roots'

    def test_find_real_path_through_a_refused_link_chain_returns_none(self) -> None:
        #: Given
        database = Database(_refused_chain_snapshot())
        path = RootRelativePath.parse('skills/l/SKILL.md')

        #: When
        resolved = database.find_real_path(path)

        #: Then
        assert resolved is None, (
            'the scan refuses ../a/tmp/../b, so skills/l/SKILL.md leads nowhere, though a/b/SKILL.md is recorded'
        )

    def test_find_real_file_through_a_refused_link_chain_returns_none(self) -> None:
        #: Given
        database = Database(_refused_chain_snapshot())
        path = RootRelativePath.parse('skills/l/SKILL.md')

        #: When
        resolved = database.find_real_file(path)

        #: Then
        assert resolved is None, (
            'the scan refuses ../a/tmp/../b, so skills/l/SKILL.md leads to no file, though a/b/SKILL.md is recorded'
        )

    def test_find_real_file_through_a_followed_link_returns_the_real_file(self) -> None:
        #: Given
        database = Database(_refused_chain_snapshot())
        path = RootRelativePath.parse('skills/m/SKILL.md')

        #: When
        resolved = database.find_real_file(path)

        #: Then
        assert resolved == RootRelativePath.parse('a/b/SKILL.md'), 'the scan follows skills/m to a/b'

    def test_frontmatter_of_a_listed_document_returns_its_decoded_block(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))

        #: When
        frontmatter = database.frontmatter(GUIDE)

        #: Then
        assert isinstance(frontmatter, Frontmatter), 'the snapshot bytes decode into a frontmatter node'
        assert frontmatter.data == {'name': 'guide'}, 'the frontmatter holds the snapshot content'

    def test_frontmatter_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))
        first = database.frontmatter(GUIDE)

        #: When
        second = database.frontmatter(GUIDE)

        #: Then
        assert second is first, 'a document frontmatter is decoded once per database, then shared by every check'

    def test_frontmatter_of_a_document_that_is_not_utf8_raises_document_decode_error(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "gu\xffide"\n---\n'))

        #: When
        with pytest.raises(DocumentDecodeError) as exc_info:
            database.frontmatter(GUIDE)

        #: Then
        assert exc_info.value.ref == GUIDE, 'the error names the document that could not be decoded'

    def test_parse_of_a_listed_document_returns_its_frontmatter(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))

        #: When
        document = database.parse(GUIDE)

        #: Then
        assert isinstance(document.frontmatter, Frontmatter), 'the snapshot bytes parse into a frontmatter node'
        assert document.frontmatter.data == {'name': 'guide'}, 'the parse tree holds the snapshot content'

    def test_parse_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "guide"\n---\n'))
        first = database.parse(GUIDE)

        #: When
        second = database.parse(GUIDE)

        #: Then
        assert second is first, 'a document is parsed once per database, then shared by every check'

    def test_parse_of_a_document_that_is_not_utf8_raises_document_decode_error(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "gu\xffide"\n---\n'))

        #: When
        with pytest.raises(DocumentDecodeError) as exc_info:
            database.parse(GUIDE)

        #: Then
        assert exc_info.value.ref == GUIDE, 'the error names the document that could not be decoded'

    def test_tokens_of_a_listed_document_counts_its_whole_file(self) -> None:
        #: Given
        # no prose words at all, but an agent loading the file still pays for every character of it
        guide = '---\nname: "guide"\n---\n```python\nx = 1\n```\n'
        database = Database(_snapshot(guide.encode()))
        expected = count_tokens(guide)

        #: When
        tokens = database.tokens(GUIDE)

        #: Then
        assert tokens == expected, f'frontmatter and code count too, got {tokens}'

    def test_tokens_of_a_document_that_is_not_utf8_raises_document_decode_error(self) -> None:
        #: Given
        database = Database(_snapshot(b'---\nname: "gu\xffide"\n---\n'))

        #: When
        with pytest.raises(DocumentDecodeError) as exc_info:
            database.tokens(GUIDE)

        #: Then
        assert exc_info.value.ref == GUIDE, 'the error names the document that could not be decoded'

    def test_skill_parse_of_a_skill_returns_its_links(self) -> None:
        #: Given
        database = Database(_skill_snapshot(b'---\nname: review\n---\n# Review\n\nSee [the guide](guide.md).\n'))

        #: When
        document = database.skill_parse(REVIEW)

        #: Then
        assert document.links == (MarkdownLink(url='guide.md', line=LineNumber(6)),), (
            'the SKILL.md bytes parse into a tree holding its links'
        )

    def test_skill_parse_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database(_skill_snapshot(b'---\nname: review\n---\n# Review\n'))
        first = database.skill_parse(REVIEW)

        #: When
        second = database.skill_parse(REVIEW)

        #: Then
        assert second is first, 'a skill is parsed once per database, then shared by every check'

    def test_skill_parse_of_a_linked_skill_parses_the_skill_the_link_leads_to(self) -> None:
        #: Given
        # What a scan records for `.agents/skills/review -> ../../skills/review`: the link in the skills directory,
        # and the SKILL.md at the real path it leads to.
        shipped = Snapshot.from_files(
            {RootRelativePath.parse('skills/review/SKILL.md'): b'---\nname: review\n---\n[the guide](guide.md)\n'}
        )
        snapshot = Snapshot(
            listings=shipped.listings,
            files=shipped.files,
            links=(Link(RootRelativePath.parse('.agents/skills/review'), PurePosixPath('../../skills/review')),),
        )
        database = Database(snapshot)

        #: When
        document = database.skill_parse(REVIEW)

        #: Then
        assert document.links == (MarkdownLink(url='guide.md', line=LineNumber(4)),), (
            'the ref names the linked entry, and the tree is parsed from the SKILL.md the link leads to'
        )

    def test_skill_parse_of_a_skill_that_is_not_utf8_raises_skill_decode_error(self) -> None:
        #: Given
        database = Database(_skill_snapshot(b'---\nname: caf\xe9\n---\n'))

        #: When
        with pytest.raises(SkillDecodeError) as exc_info:
            database.skill_parse(REVIEW)

        #: Then
        assert exc_info.value.ref == REVIEW, 'the error names the skill that could not be decoded'

    def test_skill_frontmatter_called_twice_returns_the_first_answer(self) -> None:
        #: Given
        database = Database(_skill_snapshot(b'---\nname: review\n---\n'))
        first = database.skill_frontmatter(REVIEW)

        #: When
        second = database.skill_frontmatter(REVIEW)

        #: Then
        assert isinstance(first, Frontmatter), 'the skill bytes decode into a frontmatter node'
        assert second is first, 'a skill frontmatter is decoded once per database, then shared by every check'
