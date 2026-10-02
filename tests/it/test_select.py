"""Explicit document and skill selection against a database over a snapshot of a real tree.

Documents and skills are each selected against a database over a snapshot of `tmp_path`, and every argument is
a path in that tree, so `select_document` and `select_skills_at` resolve it the way the command line does. A skill
argument naming a directory no agent reads is selected against a database whose snapshot read it, as
`select_skills` takes one. Each rule of the selection order has one test asserting the reason it produces, never
the message. `select_documents` and `select_skills` are driven with an explicit root, to pin how the documents and
the skills several paths name are merged.
"""

from pathlib import Path
from typing import Final

import pytest

from lorecraft.checks import Database, SkillScope, SkillSelection
from lorecraft.cli.check_run import select_documents, select_skills
from lorecraft.cli.select import (
    CorpuslessDocumentPathError,
    InvalidCorpusDocumentPathError,
    MissingDocumentPathError,
    NestedDocumentPathError,
    NonFileDocumentPathError,
    NonMarkdownDocumentPathError,
    OutsideDocsDocumentPathError,
    UnknownCorpusDocumentPathError,
    UnlistedDocumentPathError,
    UnlistedSkillPathError,
    named_skill_dirs,
    select_document,
    select_skills_at,
)
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName, InvalidCorpusNameCharacterError
from lorecraft.project.document import DocumentRef
from lorecraft.project.layout import SNAPSHOT_SCOPE, scope_with_named_dirs
from lorecraft.project.skill import SkillRef
from lorecraft.vfs import take_snapshot


def _write(root: Path, relative: str, text: str = '') -> Path:
    """Write one file under the root, creating its parents, and return its path.

    Args:
        root: Directory the file is written under, as the repository root.
        relative: Path of the file below `root`, with `/` separators.
        text: Content of the file, written as UTF-8. Empty by default.
    """
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


@pytest.fixture(scope='function')
def documents_database(tmp_path: Path) -> Database:
    """A database over a snapshot of one corpus `code`.

    The corpus holds `logging.md`, a misnamed `README.md` and `alias.md`, a link to `logging.md`.

    Beside the corpus sit the paths the rules reject: a nested file, a spec-less directory, an invalid
    corpus name, a file directly under `docs/` and a non-Markdown file.

    Args:
        tmp_path: Directory the tree is written into and snapshotted, as the repository root.
    """
    _write(tmp_path, 'docs/__meta__/code.md')
    _write(tmp_path, 'docs/code/logging.md')
    _write(tmp_path, 'docs/code/README.md')
    _write(tmp_path, 'docs/code/notes.txt')
    _write(tmp_path, 'docs/code/sub/x.md')
    _write(tmp_path, 'docs/schemas/tables/x.md')
    _write(tmp_path, 'docs/bad-name/guide.md')
    _write(tmp_path, 'docs/architecture.md')
    (tmp_path / 'docs' / 'code' / 'alias.md').symlink_to('logging.md')
    return Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))


@pytest.mark.it
class TestSelectDocument:
    def test_select_document_with_a_listed_document_returns_its_ref(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'code' / 'logging.md'

        #: When
        ref = select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert ref == DocumentRef(CorpusName.parse('code'), AspectFilename.parse('logging')), (
            'the argument maps onto the ref the model lists'
        )

    def test_select_document_with_a_link_in_the_snapshot_returns_the_target_ref(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'code' / 'alias.md'

        #: When
        ref = select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert ref == DocumentRef(CorpusName.parse('code'), AspectFilename.parse('logging')), (
            'the snapshot follows the link it recorded, so the alias names its target'
        )

    def test_select_document_with_a_link_outside_the_snapshot_raises_outside_docs(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'alias.md'
        argument.symlink_to(tmp_path / 'docs' / 'code' / 'logging.md')

        #: When
        with pytest.raises(OutsideDocsDocumentPathError) as exc_info:
            select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, (
            'the scan never read the link, so it is judged by its spelling, which lies outside docs/'
        )

    def test_select_document_with_a_relative_argument_resolves_it_from_the_working_directory(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        working_directory = tmp_path / 'docs' / 'code'
        argument = Path('logging.md')

        #: When
        ref = select_document(documents_database, tmp_path, working_directory, argument)

        #: Then
        assert ref == DocumentRef(CorpusName.parse('code'), AspectFilename.parse('logging')), (
            'a relative argument is spelled from the working directory'
        )

    def test_select_document_with_a_path_outside_the_root_raises_outside_docs(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = tmp_path.parent / 'elsewhere.md'

        #: When
        with pytest.raises(OutsideDocsDocumentPathError) as exc_info:
            select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, 'a path outside the root is outside docs/'

    def test_select_document_with_a_missing_file_raises_not_found(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'code' / 'missing.md'

        #: When
        with pytest.raises(MissingDocumentPathError) as exc_info:
            select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, 'the snapshot holds no file there'
        assert exc_info.value.argument == argument, 'the error quotes the argument as typed'

    def test_select_document_with_a_directory_raises_not_a_file(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'code'

        #: When
        with pytest.raises(NonFileDocumentPathError) as exc_info:
            select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, 'a directory is not a document'

    def test_select_document_with_a_txt_file_raises_not_markdown(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'code' / 'notes.txt'

        #: When
        with pytest.raises(NonMarkdownDocumentPathError) as exc_info:
            select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, 'only .md files are documents'

    def test_select_document_with_a_specification_file_raises_outside_docs(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / '__meta__' / 'code.md'

        #: When
        with pytest.raises(OutsideDocsDocumentPathError) as exc_info:
            select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, 'docs/__meta__/ holds no documents'

    def test_select_document_with_a_file_outside_docs_raises_outside_docs(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = _write(tmp_path, 'README.md')

        #: When
        with pytest.raises(OutsideDocsDocumentPathError) as exc_info:
            select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, 'a file outside docs/ is no document'

    def test_select_document_with_a_file_directly_under_docs_raises_not_in_corpus(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'architecture.md'

        #: When
        with pytest.raises(CorpuslessDocumentPathError) as exc_info:
            select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, 'a file directly under docs/ has no corpus'

    def test_select_document_with_an_invalid_corpus_name_raises_invalid_corpus_name(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'bad-name' / 'guide.md'

        #: When
        with pytest.raises(InvalidCorpusDocumentPathError) as exc_info:
            select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, 'the first segment must parse'
        assert isinstance(exc_info.value.source, InvalidCorpusNameCharacterError), (
            'the parser failure is the typed source'
        )

    def test_select_document_with_a_nested_path_under_a_spec_less_directory_raises_not_a_corpus(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'schemas' / 'tables' / 'x.md'

        #: When
        with pytest.raises(UnknownCorpusDocumentPathError) as exc_info:
            select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, (
            'the first segment is judged before depth, so the missing spec is the cause, not the nesting'
        )

    def test_select_document_with_a_nested_path_in_a_corpus_raises_nested(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'code' / 'sub' / 'x.md'

        #: When
        with pytest.raises(NestedDocumentPathError) as exc_info:
            select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, 'corpora are flat'

    def test_select_document_with_a_document_the_loader_left_out_raises_not_listed(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'code' / 'README.md'

        #: When
        with pytest.raises(UnlistedDocumentPathError) as exc_info:
            select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, (
            'a file whose stem is not a valid document name is not a listed document'
        )

    def test_select_document_with_a_file_added_after_the_snapshot_raises_not_found(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = _write(tmp_path, 'docs/code/later.md')

        #: When
        with pytest.raises(MissingDocumentPathError) as exc_info:
            select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, 'the argument is resolved in the snapshot'

    def test_select_document_with_a_file_removed_after_the_snapshot_returns_the_ref_the_snapshot_saw(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'code' / 'logging.md'
        argument.unlink()

        #: When
        ref = select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert ref == DocumentRef(CorpusName.parse('code'), AspectFilename.parse('logging')), (
            'the argument is resolved through the snapshot, not the disk'
        )

    def test_select_document_with_a_link_retargeted_after_the_snapshot_returns_the_ref_the_snapshot_saw(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'docs' / 'code' / 'alias.md'
        argument.unlink()
        argument.symlink_to('README.md')

        #: When
        ref = select_document(documents_database, tmp_path, tmp_path, argument)

        #: Then
        assert ref == DocumentRef(CorpusName.parse('code'), AspectFilename.parse('logging')), (
            'the link is followed where the snapshot saw it lead'
        )


@pytest.mark.it
class TestSelectDocuments:
    def test_select_documents_with_one_document_named_twice_selects_it_once_where_first_named(
        self, tmp_path: Path, documents_database: Database
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/code/tracing.md')
        paths = [
            tmp_path / 'docs' / 'code' / 'tracing.md',
            tmp_path / 'docs' / 'code' / 'alias.md',
            tmp_path / 'docs' / 'code' / 'logging.md',
            tmp_path / 'docs' / 'code' / 'tracing.md',
        ]

        #: When
        _database, refs = select_documents(tmp_path, paths)

        #: Then
        assert refs == (
            DocumentRef(CorpusName.parse('code'), AspectFilename.parse('tracing')),
            DocumentRef(CorpusName.parse('code'), AspectFilename.parse('logging')),
        ), 'each document once, in first-named order, the link and its target being one document'


AUDIT: Final[SkillRef] = SkillRef(RootRelativePath.parse('.agents/skills/audit'))
COMMIT: Final[SkillRef] = SkillRef(RootRelativePath.parse('.agents/skills/commit'))
LINT: Final[SkillRef] = SkillRef(RootRelativePath.parse('.agents/skills/lint'))
REVIEW: Final[SkillRef] = SkillRef(RootRelativePath.parse('.agents/skills/review'))
REVIEWER: Final[SkillRef] = SkillRef(RootRelativePath.parse('.agents/skills/reviewer'))
SKILLS_REVIEW: Final[SkillRef] = SkillRef(RootRelativePath.parse('skills/review'))
SKILLS_SOLO: Final[SkillRef] = SkillRef(RootRelativePath.parse('skills/solo'))


def _database_naming(root: Path, working_directory: Path, argument: Path) -> Database:
    """A database over a snapshot of `root` that reads the directory `argument` names, as `select_skills` takes one.

    Args:
        root: The repository root the snapshot is taken of.
        working_directory: What a relative argument is relative to.
        argument: The path as typed; the directory it names joins the snapshot and the model.
    """
    named_dirs = named_skill_dirs(root, working_directory, [argument])
    return Database(take_snapshot(root, scope_with_named_dirs(named_dirs)))


@pytest.fixture(scope='function')
def skills_database(tmp_path: Path) -> Database:
    """A database over a snapshot of `.agents/skills`.

    It holds `commit`, `review` and `reviewer` both linked to `skills/review/`, `audit` linked to `commit`, and
    `lint`, whose `SKILL.md` links to `shared/LINT.md`; `.claude/skills` links to the directory, and `drafts/` is
    no skill. `skills/` also holds `solo`, which no entry links to, so no agent reads it.

    Args:
        tmp_path: Directory the tree is written into and snapshotted, as the repository root.
    """
    _write(tmp_path, '.agents/skills/commit/SKILL.md')
    _write(tmp_path, '.agents/skills/drafts/README.md')
    _write(tmp_path, 'skills/review/SKILL.md')
    _write(tmp_path, 'skills/solo/SKILL.md')
    _write(tmp_path, 'shared/LINT.md')
    (tmp_path / '.agents' / 'skills' / 'lint').mkdir()
    (tmp_path / '.agents' / 'skills' / 'lint' / 'SKILL.md').symlink_to('../../../shared/LINT.md')
    (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
    (tmp_path / '.agents' / 'skills' / 'reviewer').symlink_to('../../skills/review')
    (tmp_path / '.agents' / 'skills' / 'audit').symlink_to('commit')
    (tmp_path / '.claude').mkdir()
    (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')
    return Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))


@pytest.mark.it
class TestSelectSkillsAt:
    def test_select_skills_at_with_a_linked_skill_directory_selects_it_whole(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / '.agents' / 'skills' / 'review'

        #: When
        selections = select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (SkillSelection(REVIEW, SkillScope.WHOLE_SKILL),), (
            'the argument maps onto the ref the model lists, and a directory selects the whole skill'
        )

    def test_select_skills_at_with_the_directory_two_entries_link_to_selects_it_as_a_skill_of_its_own(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'skills' / 'review'
        database = _database_naming(tmp_path, tmp_path, argument)

        #: When
        selections = select_skills_at(database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (SkillSelection(SKILLS_REVIEW, SkillScope.WHOLE_SKILL),), (
            'a directory with a SKILL.md at its root is one skill, named as spelled, not the entries linked to it'
        )

    def test_select_skills_at_with_a_skill_file_behind_a_linked_skills_directory_selects_the_file_alone(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / '.claude' / 'skills' / 'review' / 'SKILL.md'

        #: When
        selections = select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (SkillSelection(REVIEW, SkillScope.SKILL_FILE),), (
            'a skill is named by its SKILL.md, through any link, and that file alone is selected'
        )

    def test_select_skills_at_with_the_entry_another_entry_links_to_returns_its_ref_alone(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / '.agents' / 'skills' / 'commit'

        #: When
        selections = select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (SkillSelection(COMMIT, SkillScope.WHOLE_SKILL),), (
            'the entry named is the skill selected, not audit, which links to it'
        )

    def test_select_skills_at_with_a_linked_entry_returns_its_ref_alone(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / '.agents' / 'skills' / 'audit'

        #: When
        selections = select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (SkillSelection(AUDIT, SkillScope.WHOLE_SKILL),), (
            'the linked entry is the skill selected, not commit, where it leads'
        )

    def test_select_skills_at_with_the_skill_file_of_a_linked_entry_selects_the_file_of_that_entry_alone(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / '.agents' / 'skills' / 'audit' / 'SKILL.md'

        #: When
        selections = select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (SkillSelection(AUDIT, SkillScope.SKILL_FILE),), (
            'the SKILL.md under the linked entry names that entry alone, and that file alone of it'
        )

    def test_select_skills_at_with_a_linked_entry_behind_a_linked_skills_directory_returns_its_ref_alone(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / '.claude' / 'skills' / 'audit'

        #: When
        selections = select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (SkillSelection(AUDIT, SkillScope.WHOLE_SKILL),), (
            'the linked skills directory is followed to the resolved one, and the entry kept by name'
        )

    def test_select_skills_at_with_the_file_a_linked_skill_file_leads_to_selects_the_file_alone(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'shared' / 'LINT.md'

        #: When
        selections = select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (SkillSelection(LINT, SkillScope.SKILL_FILE),), (
            'the file a linked SKILL.md leads to names the skill too, and selects that file alone'
        )

    def test_select_skills_at_with_a_skill_file_that_is_a_link_selects_the_file_alone(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / '.agents' / 'skills' / 'lint' / 'SKILL.md'

        #: When
        selections = select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (SkillSelection(LINT, SkillScope.SKILL_FILE),), (
            'the linked SKILL.md resolves to the file the model records for the skill, selected alone'
        )

    def test_select_skills_at_with_the_skill_file_of_a_directory_two_entries_link_to_selects_its_file_alone(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'skills' / 'review' / 'SKILL.md'
        database = _database_naming(tmp_path, tmp_path, argument)

        #: When
        selections = select_skills_at(database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (SkillSelection(SKILLS_REVIEW, SkillScope.SKILL_FILE),), (
            'the SKILL.md names the skill its directory is, as spelled, and that file alone of it'
        )

    def test_select_skills_at_with_a_path_outside_the_root_raises_not_listed(
        self, tmp_path: Path, skills_database: Database, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        #: Given
        argument = tmp_path_factory.mktemp('outside')

        #: When
        with pytest.raises(UnlistedSkillPathError) as exc_info:
            select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, 'no skill the model lists is outside the root'

    def test_select_skills_at_with_a_root_reached_through_a_link_above_it_returns_its_ref(
        self, tmp_path: Path, skills_database: Database, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        #: Given
        link = tmp_path_factory.mktemp('links') / 'workspace'
        link.symlink_to(tmp_path)
        argument = link / '.agents' / 'skills' / 'commit'

        #: When
        selections = select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (SkillSelection(COMMIT, SkillScope.WHOLE_SKILL),), (
            'a link above the root is followed on disk, where the snapshot records nothing'
        )

    def test_select_skills_at_through_a_link_above_the_root_and_one_added_under_it_raises_not_listed(
        self, tmp_path: Path, skills_database: Database, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        #: Given
        link = tmp_path_factory.mktemp('links') / 'workspace'
        link.symlink_to(tmp_path)
        (tmp_path / 'self').symlink_to('.')
        argument = link / 'self' / '.agents' / 'skills' / 'commit'

        #: When
        with pytest.raises(UnlistedSkillPathError) as exc_info:
            select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, (
            'only the link above the root is followed on disk; self, added after the snapshot, leads nowhere'
        )

    def test_select_skills_at_with_a_skills_directory_selects_every_skill_listed_in_it_whole(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / '.agents' / 'skills'

        #: When
        selections = select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (
            SkillSelection(AUDIT, SkillScope.WHOLE_SKILL),
            SkillSelection(COMMIT, SkillScope.WHOLE_SKILL),
            SkillSelection(LINT, SkillScope.WHOLE_SKILL),
            SkillSelection(REVIEW, SkillScope.WHOLE_SKILL),
            SkillSelection(REVIEWER, SkillScope.WHOLE_SKILL),
        ), 'every entry of the skills directory, linked or not, each once, in the model order'

    def test_select_skills_at_with_a_linked_skills_directory_returns_the_refs_of_the_resolved_one(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / '.claude' / 'skills'

        #: When
        selections = select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (
            SkillSelection(AUDIT, SkillScope.WHOLE_SKILL),
            SkillSelection(COMMIT, SkillScope.WHOLE_SKILL),
            SkillSelection(LINT, SkillScope.WHOLE_SKILL),
            SkillSelection(REVIEW, SkillScope.WHOLE_SKILL),
            SkillSelection(REVIEWER, SkillScope.WHOLE_SKILL),
        ), 'the link is followed to the resolved skills directory, and its skills keep their refs there'

    def test_select_skills_at_with_a_skills_directory_holding_no_skill_returns_empty(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))
        argument = tmp_path / '.agents' / 'skills'

        #: When
        selections = select_skills_at(database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (), 'a skills directory with no skill is a selection of none, not a refusal'

    def test_select_skills_at_with_a_directory_of_skills_no_agent_reads_selects_each_skill_in_it_whole(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'skills'
        database = _database_naming(tmp_path, tmp_path, argument)

        #: When
        selections = select_skills_at(database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (
            SkillSelection(SKILLS_REVIEW, SkillScope.WHOLE_SKILL),
            SkillSelection(SKILLS_SOLO, SkillScope.WHOLE_SKILL),
        ), 'each directory in it holding a SKILL.md is a skill, named under it, solo too, which no entry links to'

    def test_select_skills_at_with_a_link_to_a_directory_of_skills_names_each_skill_under_the_link(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        (tmp_path / 'bundle').symlink_to('skills')
        argument = tmp_path / 'bundle'
        database = _database_naming(tmp_path, tmp_path, argument)

        #: When
        selections = select_skills_at(database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (
            SkillSelection(SkillRef(RootRelativePath.parse('bundle/review')), SkillScope.WHOLE_SKILL),
            SkillSelection(SkillRef(RootRelativePath.parse('bundle/solo')), SkillScope.WHOLE_SKILL),
        ), 'the link is followed to the directory, and each skill keeps the spelling of the path named'

    def test_select_skills_at_with_a_directory_holding_a_link_to_a_skill_selects_it_by_the_link(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        (tmp_path / 'bundle').mkdir()
        (tmp_path / 'bundle' / 'solo').symlink_to('../skills/solo')
        argument = tmp_path / 'bundle'
        database = _database_naming(tmp_path, tmp_path, argument)

        #: When
        selections = select_skills_at(database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (
            SkillSelection(SkillRef(RootRelativePath.parse('bundle/solo')), SkillScope.WHOLE_SKILL),
        ), 'an entry linked to a skill directory is a skill named by the entry'

    def test_select_skills_at_with_a_directory_holding_no_skill_raises_not_listed(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / 'shared'
        database = _database_naming(tmp_path, tmp_path, argument)

        #: When
        with pytest.raises(UnlistedSkillPathError) as exc_info:
            select_skills_at(database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, (
            'a directory with no SKILL.md at its root or in a directory inside it names no skill'
        )

    def test_select_skills_at_with_a_link_leading_outside_the_repository_selects_none(
        self, tmp_path: Path, skills_database: Database, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        #: Given
        outside = tmp_path_factory.mktemp('outside')
        _write(outside, 'review/SKILL.md')
        (tmp_path / 'elsewhere').symlink_to(outside)
        argument = tmp_path / 'elsewhere'
        database = _database_naming(tmp_path, tmp_path, argument)

        #: When
        selections = select_skills_at(database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (), 'the link is never followed out, so no skill is selected and the run reports it'

    def test_select_skills_at_with_a_directory_whose_only_entry_leads_outside_selects_none(
        self, tmp_path: Path, skills_database: Database, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        #: Given
        outside = tmp_path_factory.mktemp('outside')
        _write(outside, 'x/SKILL.md')
        (tmp_path / 'onlyout').mkdir()
        (tmp_path / 'onlyout' / 'x').symlink_to(outside / 'x')
        argument = tmp_path / 'onlyout'
        database = _database_naming(tmp_path, tmp_path, argument)

        #: When
        selections = select_skills_at(database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (), (
            "a directory holding only a link leading outside selects none, as an agent's skills directory does"
        )

    def test_select_skills_at_with_a_skill_file_leading_outside_selects_none(
        self, tmp_path: Path, skills_database: Database, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        #: Given
        outside = tmp_path_factory.mktemp('outside')
        _write(outside, 'audit.md')
        (tmp_path / 'skills' / 'audit').mkdir()
        (tmp_path / 'skills' / 'audit' / 'SKILL.md').symlink_to(outside / 'audit.md')
        argument = tmp_path / 'skills' / 'audit' / 'SKILL.md'
        database = _database_naming(tmp_path, tmp_path, argument)

        #: When
        selections = select_skills_at(database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (), 'the SKILL.md named leads outside, so it is reported, not checked nor refused'

    def test_select_skills_at_with_the_parent_of_an_agent_skills_directory_raises_not_listed(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / '.agents'
        database = _database_naming(tmp_path, tmp_path, argument)

        #: When
        with pytest.raises(UnlistedSkillPathError) as exc_info:
            select_skills_at(database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, (
            'skills/ under .agents holds no SKILL.md of its own, so .agents is neither a skill nor holds one'
        )

    def test_select_skills_at_with_a_trailing_slash_selects_as_without_it(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = Path(f'{tmp_path / "skills"}/')
        database = _database_naming(tmp_path, tmp_path, argument)

        #: When
        selections = select_skills_at(database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (
            SkillSelection(SKILLS_REVIEW, SkillScope.WHOLE_SKILL),
            SkillSelection(SKILLS_SOLO, SkillScope.WHOLE_SKILL),
        ), 'a trailing slash names the same directory'

    def test_select_skills_at_with_the_root_raises_not_listed(self, tmp_path: Path, skills_database: Database) -> None:
        #: Given
        _write(tmp_path, 'SKILL.md')
        argument = tmp_path
        database = _database_naming(tmp_path, tmp_path, argument)

        #: When
        with pytest.raises(UnlistedSkillPathError) as exc_info:
            select_skills_at(database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, 'the root is never read as a skill, which would read it whole'

    def test_select_skills_at_with_a_directory_that_is_no_skill_raises_not_listed(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / '.agents' / 'skills' / 'drafts'

        #: When
        with pytest.raises(UnlistedSkillPathError) as exc_info:
            select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, 'a directory with no SKILL.md is not a skill'

    def test_select_skills_at_with_a_missing_path_raises_not_listed(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        argument = tmp_path / '.agents' / 'skills' / 'missing'

        #: When
        with pytest.raises(UnlistedSkillPathError) as exc_info:
            select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, 'the snapshot holds nothing at the path'

    def test_select_skills_at_with_a_relative_argument_resolves_it_from_the_working_directory(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        working_directory = tmp_path / '.agents' / 'skills'
        argument = Path('../../skills/review')
        database = _database_naming(tmp_path, working_directory, argument)

        #: When
        selections = select_skills_at(database, tmp_path, working_directory, argument)

        #: Then
        assert selections == (SkillSelection(SKILLS_REVIEW, SkillScope.WHOLE_SKILL),), (
            'a relative argument is spelled from the working directory, `..` included'
        )

    def test_select_skills_at_with_a_link_removed_after_the_snapshot_returns_the_ref_the_snapshot_saw(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        (tmp_path / '.agents' / 'skills' / 'review').unlink()
        argument = tmp_path / '.agents' / 'skills' / 'review'

        #: When
        selections = select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert selections == (SkillSelection(REVIEW, SkillScope.WHOLE_SKILL),), (
            'the argument is resolved through the snapshot, not the disk'
        )

    def test_select_skills_at_with_a_link_added_after_the_snapshot_raises_not_listed(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        (tmp_path / '.agents' / 'skills' / 'lint-alias').symlink_to('lint')
        argument = tmp_path / '.agents' / 'skills' / 'lint-alias'

        #: When
        with pytest.raises(UnlistedSkillPathError) as exc_info:
            select_skills_at(skills_database, tmp_path, tmp_path, argument)

        #: Then
        assert exc_info.value.argument == argument, 'a link the snapshot never saw leads nowhere'


@pytest.mark.it
class TestSelectSkills:
    def test_select_skills_with_a_skill_directory_and_its_skill_file_selects_it_whole_once(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        paths = [tmp_path / '.agents' / 'skills' / 'commit' / 'SKILL.md', tmp_path / '.agents' / 'skills' / 'commit']

        #: When
        _database, selections = select_skills(tmp_path, paths)

        #: Then
        assert selections == (SkillSelection(COMMIT, SkillScope.WHOLE_SKILL),), (
            'the skill is selected once, whole, though its SKILL.md was named first'
        )

    def test_select_skills_with_a_skill_file_and_its_skills_directory_selects_every_skill_whole(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        paths = [tmp_path / '.agents' / 'skills' / 'lint' / 'SKILL.md', tmp_path / '.claude' / 'skills']

        #: When
        _database, selections = select_skills(tmp_path, paths)

        #: Then
        assert selections == (
            SkillSelection(LINT, SkillScope.WHOLE_SKILL),
            SkillSelection(AUDIT, SkillScope.WHOLE_SKILL),
            SkillSelection(COMMIT, SkillScope.WHOLE_SKILL),
            SkillSelection(REVIEW, SkillScope.WHOLE_SKILL),
            SkillSelection(REVIEWER, SkillScope.WHOLE_SKILL),
        ), 'each skill once, in first-named order, whole wherever any path named it whole'

    def test_select_skills_with_two_names_of_one_skill_file_selects_the_file_once(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        paths = [tmp_path / '.agents' / 'skills' / 'lint' / 'SKILL.md', tmp_path / 'shared' / 'LINT.md']

        #: When
        _database, selections = select_skills(tmp_path, paths)

        #: Then
        assert selections == (SkillSelection(LINT, SkillScope.SKILL_FILE),), (
            'two names of one SKILL.md select it once, and still the file alone'
        )

    def test_select_skills_with_an_entry_and_the_directory_it_links_to_selects_two_skills(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        paths = [tmp_path / '.agents' / 'skills' / 'review', tmp_path / 'skills' / 'review']

        #: When
        _database, selections = select_skills(tmp_path, paths)

        #: Then
        assert selections == (
            SkillSelection(REVIEW, SkillScope.WHOLE_SKILL),
            SkillSelection(SKILLS_REVIEW, SkillScope.WHOLE_SKILL),
        ), 'each path names the skill by its own spelling, so the one directory is two skills'

    def test_select_skills_with_a_directory_of_skills_and_one_skill_in_it_selects_that_skill_once(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        paths = [tmp_path / 'skills' / 'solo' / 'SKILL.md', tmp_path / 'skills']

        #: When
        _database, selections = select_skills(tmp_path, paths)

        #: Then
        assert selections == (
            SkillSelection(SKILLS_SOLO, SkillScope.WHOLE_SKILL),
            SkillSelection(SKILLS_REVIEW, SkillScope.WHOLE_SKILL),
        ), 'the skill both name is one, selected where first named, whole since the directory names it whole'

    def test_select_skills_with_a_skill_and_a_skill_nested_in_it_selects_both(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        _write(tmp_path, 'skills/solo/nested/SKILL.md')
        paths = [tmp_path / 'skills' / 'solo' / 'nested', tmp_path / 'skills' / 'solo']

        #: When
        _database, selections = select_skills(tmp_path, paths)

        #: Then
        assert selections == (
            SkillSelection(SkillRef(RootRelativePath.parse('skills/solo/nested')), SkillScope.WHOLE_SKILL),
            SkillSelection(SKILLS_SOLO, SkillScope.WHOLE_SKILL),
        ), 'each directory named with a SKILL.md at its root is a skill of its own, the nested one too'

    def test_select_skills_with_a_directory_an_agent_skills_directory_links_to_selects_the_agents_skills(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'skills/review/SKILL.md')
        (tmp_path / '.agents').mkdir()
        (tmp_path / '.agents' / 'skills').symlink_to('../skills')
        paths = [tmp_path / 'skills']

        #: When
        database, selections = select_skills(tmp_path, paths)

        #: Then
        assert database.model().named_dirs == (), "the directory is an agent's skills directory, read the agents' way"
        assert selections == (SkillSelection(SKILLS_REVIEW, SkillScope.WHOLE_SKILL),), (
            'every skill the agent lists there is selected, under the resolved skills directory'
        )

    def test_select_skills_with_no_path_selects_every_skill_whole(
        self, tmp_path: Path, skills_database: Database
    ) -> None:
        #: Given
        paths = None

        #: When
        _database, selections = select_skills(tmp_path, paths)

        #: Then
        assert selections == (
            SkillSelection(AUDIT, SkillScope.WHOLE_SKILL),
            SkillSelection(COMMIT, SkillScope.WHOLE_SKILL),
            SkillSelection(LINT, SkillScope.WHOLE_SKILL),
            SkillSelection(REVIEW, SkillScope.WHOLE_SKILL),
            SkillSelection(REVIEWER, SkillScope.WHOLE_SKILL),
        ), 'a run naming no path checks every skill whole'


@pytest.mark.it
class TestNamedSkillDirs:
    def test_named_skill_dirs_with_a_directory_named_twice_returns_it_once(self, tmp_path: Path) -> None:
        #: Given
        arguments = [tmp_path / 'skills', Path('skills'), tmp_path / 'shared']

        #: When
        directories = named_skill_dirs(tmp_path, tmp_path, arguments)

        #: Then
        assert directories == (RootRelativePath.parse('skills'), RootRelativePath.parse('shared')), (
            'each directory once, in the order first named, however it is spelled to the same path'
        )

    def test_named_skill_dirs_with_a_skill_file_returns_the_directory_holding_it(self, tmp_path: Path) -> None:
        #: Given
        arguments = [tmp_path / 'skills' / 'review' / 'SKILL.md']

        #: When
        directories = named_skill_dirs(tmp_path, tmp_path, arguments)

        #: Then
        assert directories == (RootRelativePath.parse('skills/review'),), 'a SKILL.md names the directory holding it'

    def test_named_skill_dirs_with_a_path_outside_the_root_leaves_it_out(
        self, tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        #: Given
        arguments = [tmp_path_factory.mktemp('outside'), tmp_path / 'skills']

        #: When
        directories = named_skill_dirs(tmp_path, tmp_path, arguments)

        #: Then
        assert directories == (RootRelativePath.parse('skills'),), 'a path outside the root names no directory under it'

    def test_named_skill_dirs_with_a_relative_argument_spells_it_from_the_working_directory(
        self, tmp_path: Path
    ) -> None:
        #: Given
        working_directory = tmp_path / '.agents' / 'skills'
        arguments = [Path('../../skills/review/')]

        #: When
        directories = named_skill_dirs(tmp_path, working_directory, arguments)

        #: Then
        assert directories == (RootRelativePath.parse('skills/review'),), (
            'the argument is spelled from the working directory, `..` and a trailing slash taken lexically'
        )
