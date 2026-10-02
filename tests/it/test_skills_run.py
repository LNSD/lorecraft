"""The skill run over a database opened on a snapshot of a real tree.

``run_skills`` reads everything through the database, and the database answers from one snapshot, so the run
reports the skills as the scan saw them, through whichever link an agent reaches each by.
"""

from pathlib import Path
from typing import Final

import pytest

from lorecraft.checks import (
    Database,
    Finding,
    Note,
    NoteKind,
    SkillCheckRun,
    SkillReport,
    SkillScope,
    SkillSelection,
    Violation,
    run_skills,
)
from lorecraft.core.path import RootRelativePath
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.skill import SkillRef
from lorecraft.project.syntax import LineNumber
from lorecraft.vfs import take_snapshot


def _write(root: Path, relative: str, data: bytes = b'') -> Path:
    """Write one file under the root, creating its parents, and return its path.

    Args:
        root: Directory the file is written under, as the repository root.
        relative: Path of the file below `root`, with `/` separators.
        data: Bytes written to the file, so a test can write content that is not UTF-8. Empty by default.
    """
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _run_every_skill(database: Database) -> SkillCheckRun:
    """Check every skill the database's model lists, each whole.

    Args:
        database: Database over the snapshot whose skills are checked.
    """
    selections: list[SkillSelection] = []
    for ref in database.model().skills():
        selections.append(SkillSelection(ref, SkillScope.WHOLE_SKILL))
    return run_skills(database, tuple(selections))


@pytest.fixture(scope='function')
def skills_tree(tmp_path: Path) -> Path:
    """A root whose skills produce every kind of report.

    Under `.agents/skills/`: `clean` conforms; `misnamed` names another skill; `undescribed` has no
    description; `bare` has no frontmatter; `latin` is not UTF-8; `extended` uses a field outside the
    specification; and `shipped` is a link to `skills/shipped/`, outside the skills directories, which
    conforms.

    Args:
        tmp_path: Directory the tree is written into, as the repository root; returned.
    """
    skills = '.agents/skills'
    _write(tmp_path, f'{skills}/clean/SKILL.md', b'---\nname: clean\ndescription: A clean skill\n---\n')
    _write(tmp_path, f'{skills}/misnamed/SKILL.md', b'---\nname: other\ndescription: Named wrong\n---\n')
    _write(tmp_path, f'{skills}/undescribed/SKILL.md', b'---\nname: undescribed\n---\n')
    _write(tmp_path, f'{skills}/bare/SKILL.md', b'# No frontmatter\n')
    _write(tmp_path, f'{skills}/latin/SKILL.md', b'---\nname: caf\xe9\n---\n')
    _write(tmp_path, f'{skills}/extended/SKILL.md', b'---\nname: extended\ndescription: Extended\nmodel: opus\n---\n')
    _write(tmp_path, 'skills/shipped/SKILL.md', b'---\nname: shipped\ndescription: Shipped from skills/\n---\n')
    (tmp_path / '.agents' / 'skills' / 'shipped').symlink_to('../../skills/shipped')
    return tmp_path


@pytest.mark.it
class TestRunSkills:
    def test_run_skills_over_a_snapshot_reports_one_rule_per_broken_skill(self, skills_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skills_tree, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        rules = [(str(finding.path), finding.line.value, finding.rule) for finding in run.findings()]
        assert rules == [
            ('.agents/skills/bare/SKILL.md', 1, 'skill.frontmatter-missing'),
            ('.agents/skills/extended/SKILL.md', 4, 'skill.unknown-field'),
            ('.agents/skills/latin/SKILL.md', 1, 'skill.undecodable'),
            ('.agents/skills/misnamed/SKILL.md', 2, 'skill.name-matches-directory'),
            ('.agents/skills/undescribed/SKILL.md', 1, 'skill.description'),
        ], 'each broken skill yields exactly the finding its defect names, in the order the model lists them'

    def test_run_skills_over_a_snapshot_reports_every_skill_it_was_handed(self, skills_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skills_tree, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [str(report.ref.directory) for report in run.reports] == [
            '.agents/skills/bare',
            '.agents/skills/clean',
            '.agents/skills/extended',
            '.agents/skills/latin',
            '.agents/skills/misnamed',
            '.agents/skills/shipped',
            '.agents/skills/undescribed',
        ], 'one report per skill, clean ones included, the linked skill among them'

    def test_run_skills_over_a_snapshot_reads_a_skill_linked_outside_the_skills_directories(
        self, skills_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(skills_tree, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        shipped = [report for report in run.reports if report.ref.directory.name == 'shipped']
        assert [report.violations for report in shipped] == [()], (
            'the linked skill is read through its link and found clean, not reported as unreadable'
        )

    def test_run_skills_after_the_disk_changes_reports_the_skills_the_snapshot_saw(self, skills_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(skills_tree, SNAPSHOT_SCOPE))
        _write(
            skills_tree, '.agents/skills/bare/SKILL.md', b'---\nname: bare\ndescription: Fixed after the scan\n---\n'
        )

        #: When
        run = _run_every_skill(database)

        #: Then
        bare = [finding.rule for finding in run.findings() if finding.path.parent.name == 'bare']
        assert bare == ['skill.frontmatter-missing'], 'the run reads the snapshot, not the disk as it is now'

    def test_run_skills_with_the_wrong_name_written_last_reports_it_and_the_repetition_on_that_line(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            b'---\nname: review\ndescription: Review a change\nname: audit\n---\n',
        )
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [report.violations for report in run.reports] == [
            (
                Violation(
                    line=LineNumber(4),
                    rule='skill.name-matches-directory',
                    message="`name` is 'audit'; expected 'review', the name of the skill directory",
                ),
                Violation(
                    line=LineNumber(4),
                    rule='skill.duplicate-key',
                    message="'name' is already written on line 2",
                ),
            )
        ], 'the name the decoder kept is judged on the last line it is written on, beside the repetition'

    def test_run_skills_with_the_right_name_written_last_reports_only_the_repetition(self, tmp_path: Path) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            b'---\nname: audit\ndescription: Review a change\nname: review\n---\n',
        )
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [report.violations for report in run.reports] == [
            (
                Violation(
                    line=LineNumber(4),
                    rule='skill.duplicate-key',
                    message="'name' is already written on line 2",
                ),
            )
        ], 'the decoder kept the right name, so the overwritten wrong one is reported only as a repetition'

    def test_run_skills_with_a_scalar_its_tag_cannot_construct_reports_it_and_checks_the_rest(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/clean/SKILL.md', b'---\nname: clean\ndescription: A clean skill\n---\n')
        _write(tmp_path, '.agents/skills/review/SKILL.md', b'---\nname: review\ndescription: !!bool maybe\n---\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [report.violations for report in run.reports] == [
            (),
            (
                Violation(
                    line=LineNumber(3),
                    rule='skill.frontmatter-unparseable',
                    message=(
                        'frontmatter is not valid YAML: '
                        "could not construct a value for the tag 'tag:yaml.org,2002:bool'"
                    ),
                ),
            ),
        ], 'the scalar is one finding on its line, and the run goes on to check the other skill'

    def test_run_skills_with_an_absolute_link_reports_it_after_the_frontmatter_findings(self, tmp_path: Path) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            b'---\nname: audit\ndescription: Review a change\n---\n# Review\n\nRead [the guide](/docs/guide.md).\n',
        )
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [report.violations for report in run.reports] == [
            (
                Violation(
                    line=LineNumber(2),
                    rule='skill.name-matches-directory',
                    message="`name` is 'audit'; expected 'review', the name of the skill directory",
                ),
                Violation(
                    line=LineNumber(7),
                    rule='skill.link-absolute',
                    message='`/docs/guide.md` is absolute',
                    notes=(Note(NoteKind.HELP, 'link relative to the skill root'),),
                ),
            )
        ], 'the link is checked beside the frontmatter, and its finding follows the frontmatter findings'

    def test_run_skills_with_an_absolute_link_in_a_linked_skill_reports_it_where_the_agent_finds_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(
            tmp_path,
            'skills/review/SKILL.md',
            b'---\nname: review\ndescription: Review a change\n---\n![flow](/assets/flow.png)\n',
        )
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/review/SKILL.md'),
                line=LineNumber(5),
                rule='skill.link-absolute',
                message='`/assets/flow.png` is absolute',
                notes=(Note(NoteKind.HELP, 'link relative to the skill root'),),
            ),
        ), 'the linked skill is parsed through its link, and the finding names the SKILL.md under the skills directory'

    def test_run_skills_with_fragment_links_reports_only_the_one_naming_a_missing_heading(self, tmp_path: Path) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            b'---\nname: review\ndescription: Review a change\n---\n# Review\n\n'
            b'See [the steps](#the-steps) and [the checklist](#checklist).\n\n- ## The steps\n',
        )
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/review/SKILL.md'),
                line=LineNumber(7),
                rule='skill.link-fragment',
                message='`#checklist` names a heading this file does not have',
            ),
        ), "the fragments are checked against the SKILL.md's own headings, a nested one included"

    def test_run_skills_with_a_fragment_naming_a_non_ascii_heading_reports_only_the_missing_one(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            '---\nname: review\ndescription: Review a change\n---\n# Straße\n\n'
            'See [x](#straße) and [y](#missing).\n'.encode(),
        )
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/review/SKILL.md'),
                line=LineNumber(7),
                rule='skill.link-fragment',
                message='`#missing` names a heading this file does not have',
            ),
        ), 'the parser percent-encodes the non-ASCII fragment, and it still matches the heading it names'

    def test_run_skills_with_a_dangling_fragment_in_a_linked_skill_reports_it_where_the_agent_finds_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(
            tmp_path,
            'skills/review/SKILL.md',
            b'---\nname: review\ndescription: Review a change\n---\n# Review\n\nSee [the checklist](#checklist).\n',
        )
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/review/SKILL.md'),
                line=LineNumber(7),
                rule='skill.link-fragment',
                message='`#checklist` names a heading this file does not have',
            ),
        ), 'the linked skill is parsed through its link, and the finding names the SKILL.md under the skills directory'

    def test_run_skills_with_an_undecodable_skill_reports_only_that_it_is_undecodable(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/latin/SKILL.md', b'---\nname: latin\n---\n[caf\xe9](/abs.md)\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [finding.rule for finding in run.findings()] == ['skill.undecodable'], (
            'a skill that is not UTF-8 is never parsed, so no link finding joins the undecodable one'
        )


def _write_skill(root: Path, metadata: str) -> None:
    """Write the skill `.agents/skills/x/`, a plain directory, with its `metadata` block on line 4.

    Args:
        root: Directory the skill is written under, as the repository root.
        metadata: The lines of the `metadata` mapping, each indented and ending in a newline.
    """
    _write(
        root, '.agents/skills/x/SKILL.md', f'---\nname: x\ndescription: A skill\nmetadata:\n{metadata}---\n'.encode()
    )


@pytest.mark.it
class TestRunSkillsMetadata:
    def test_run_skills_with_a_skill_repeating_a_file_name_reports_it_on_the_metadata_line(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/code/a.md')
        _write(tmp_path, 'docs/feat/a.md')
        _write_skill(tmp_path, '  references: docs/code/a.md docs/feat/a.md\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/x/SKILL.md'),
                line=LineNumber(4),
                rule='skill.metadata-duplicate-name',
                message=(
                    '`metadata.references` lists `docs/code/a.md` and `docs/feat/a.md`, '
                    'which both link in as `references/a.md`'
                ),
            ),
        ), 'writing a references list opts the skill into the convention, so the later path is reported'

    def test_run_skills_with_metadata_listing_no_files_reports_nothing(self, tmp_path: Path) -> None:
        #: Given
        _write_skill(tmp_path, '  author: someone\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (), 'a skill whose metadata has no references, scripts or assets links nothing in'

    def test_run_skills_with_a_skill_listing_a_source_file_reports_it_outside_the_scope(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/code/a.md')
        _write(tmp_path, 'src/tool.py')
        _write_skill(tmp_path, '  references: docs/code/a.md\n  scripts: src/tool.py\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/x/SKILL.md'),
                line=LineNumber(4),
                rule='skill.metadata-outside-scope',
                message=(
                    '`metadata.scripts` lists `src/tool.py`, which lorecraft does not read; list a file directly '
                    'in docs/, in a directory directly in docs/, or anywhere in a skill directory'
                ),
            ),
        ), 'src/ is never read, so the file there is outside the scope, while the document under docs/ is in it'

    def test_run_skills_with_a_skill_listing_a_nested_document_reports_it_outside_the_scope(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/feat/deep/a.md')
        _write_skill(tmp_path, '  references: docs/feat/deep/a.md\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [finding.rule for finding in run.findings()] == ['skill.metadata-outside-scope'], (
            'docs/ is read one level deep, so a document two levels under it is outside the scope'
        )

    def test_run_skills_with_a_skill_listing_the_docs_directory_itself_reports_it_outside_the_scope(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/a.md')
        _write_skill(tmp_path, '  references: docs\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [finding.rule for finding in run.findings()] == ['skill.metadata-outside-scope'], (
            'a scan root is listed by its parent, so the root itself is not inside what it covers'
        )

    def test_run_skills_with_a_skill_listing_a_path_climbing_out_reports_it_outside_the_scope(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write_skill(tmp_path, '  references: ../elsewhere/a.md\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [finding.rule for finding in run.findings()] == ['skill.metadata-outside-scope'], (
            'a path that is not root-relative names nothing the snapshot can read'
        )

    def test_run_skills_with_a_skill_listing_its_own_file_reports_nothing(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/x/template.json')
        _write_skill(tmp_path, '  assets: .agents/skills/x/template.json\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (), 'the skill directory is listed, so a file in it is in the scope'

    def test_run_skills_with_a_skill_listing_a_file_nested_inside_it_reports_nothing(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/x/references/deep/q.md')
        _write_skill(tmp_path, '  references: .agents/skills/x/references/deep/q.md\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (), 'every directory of a skill is read, at any depth, so a nested file is present'

    def test_run_skills_with_a_skill_listing_an_absent_file_nested_inside_it_reports_it_missing(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write_skill(tmp_path, '  references: .agents/skills/x/references/deep/q.md\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/x/SKILL.md'),
                line=LineNumber(4),
                rule='skill.metadata-missing-file',
                message=(
                    '`metadata.references` lists `.agents/skills/x/references/deep/q.md`, where lorecraft finds no file'
                ),
            ),
        ), 'a directory nested in a skill is in the scope even where the disk lacks it, so the file is missing'

    def test_run_skills_with_a_skill_listing_an_absent_document_reports_it_missing(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/feat/present.md')
        _write_skill(tmp_path, '  references: docs/feat/absent.md\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/x/SKILL.md'),
                line=LineNumber(4),
                rule='skill.metadata-missing-file',
                message='`metadata.references` lists `docs/feat/absent.md`, where lorecraft finds no file',
            ),
        ), 'docs/feat/ is listed, so a file it lacks was not there when the scan ran'

    def test_run_skills_with_a_skill_listing_a_directory_reports_it_missing(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/code/a.md')
        _write_skill(tmp_path, '  references: docs/code\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [finding.rule for finding in run.findings()] == ['skill.metadata-missing-file'], (
            'a directory is not a file to link in, and docs/ is listed, so the path is missing a file'
        )

    def test_run_skills_with_a_skill_listing_a_dangling_link_reports_it_missing(self, tmp_path: Path) -> None:
        #: Given
        (tmp_path / 'docs' / 'feat').mkdir(parents=True)
        (tmp_path / 'docs' / 'feat' / 'dangling.md').symlink_to('absent.md')
        _write_skill(tmp_path, '  references: docs/feat/dangling.md\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [finding.rule for finding in run.findings()] == ['skill.metadata-missing-file'], (
            'a link that leads to no file is no file to link in, in a directory the scope covers'
        )

    def test_run_skills_with_a_skill_listing_a_link_out_of_the_repository_reports_it_missing(
        self, tmp_path: Path
    ) -> None:
        #: Given
        root = tmp_path / 'repository'
        _write(tmp_path, 'elsewhere/a.md', b'# Elsewhere\n')
        (root / 'docs' / 'feat').mkdir(parents=True)
        (root / 'docs' / 'feat' / 'a.md').symlink_to('../../../elsewhere/a.md')
        _write_skill(root, '  references: docs/feat/a.md\n')
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [finding.rule for finding in run.findings()] == ['skill.metadata-missing-file'], (
            'a link out of the repository leads to nothing the snapshot holds, though a file is there on disk'
        )

    def test_run_skills_with_a_skill_listing_a_link_to_an_unread_file_reports_it_missing(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'src/tool.py')
        (tmp_path / 'docs' / 'feat').mkdir(parents=True)
        (tmp_path / 'docs' / 'feat' / 'x.md').symlink_to('../../src/tool.py')
        _write_skill(tmp_path, '  references: docs/feat/x.md\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [finding.rule for finding in run.findings()] == ['skill.metadata-missing-file'], (
            'a link to a repository file the snapshot never reads leads to no file it holds, in a listed directory'
        )

    def test_run_skills_with_a_skill_listing_a_link_to_a_present_document_reports_nothing(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/feat/a.md')
        (tmp_path / 'docs' / 'feat' / 'l.md').symlink_to('a.md')
        _write_skill(tmp_path, '  references: docs/feat/l.md\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (), 'a link to a file the snapshot holds is present, reached through the link'

    def test_run_skills_with_a_linked_skill_listing_an_absent_file_of_its_own_reports_it_missing(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(
            tmp_path,
            'skills/y/SKILL.md',
            b'---\nname: y\ndescription: A skill\nmetadata:\n  assets: skills/y/absent.md\n---\n',
        )
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'y').symlink_to('../../skills/y')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/y/SKILL.md'),
                line=LineNumber(4),
                rule='skill.metadata-missing-file',
                message='`metadata.assets` lists `skills/y/absent.md`, where lorecraft finds no file',
            ),
        ), 'skills/y/ is listed through the link to it, so a file it lacks was not there when the scan ran'

    def test_run_skills_with_a_skill_listing_a_document_in_an_absent_directory_reports_it_missing(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/feat/present.md')
        _write_skill(tmp_path, '  references: docs/nope/a.md\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/x/SKILL.md'),
                line=LineNumber(4),
                rule='skill.metadata-missing-file',
                message='`metadata.references` lists `docs/nope/a.md`, where lorecraft finds no file',
            ),
        ), 'docs/ is read one level deep, so docs/nope/ is in the scope though it does not exist, and a.md is missing'

    def test_run_skills_with_a_skill_listing_a_file_in_an_absent_skill_directory_reports_it_missing(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write_skill(tmp_path, '  assets: .agents/skills/nope/a.json\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [finding.rule for finding in run.findings()] == ['skill.metadata-missing-file'], (
            'a skills directory is read one level deep, so a skill directory it lacks is in the scope and empty'
        )

    def test_run_skills_with_a_skill_listing_a_document_through_an_unfollowed_docs_link_reports_it_outside_the_scope(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'elsewhere/a.md')
        (tmp_path / 'docs').mkdir()
        (tmp_path / 'docs' / 'linked').symlink_to('../elsewhere')
        _write_skill(tmp_path, '  references: docs/linked/a.md\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [finding.rule for finding in run.findings()] == ['skill.metadata-outside-scope'], (
            'docs/ does not follow links, and elsewhere/, where docs/linked leads, is in no scan root'
        )

    def test_run_skills_with_a_skill_listing_an_absent_document_through_a_docs_link_to_a_corpus_reports_it_missing(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/feat/present.md')
        (tmp_path / 'docs' / 'alias').symlink_to('feat')
        _write_skill(tmp_path, '  references: docs/alias/absent.md\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [finding.rule for finding in run.findings()] == ['skill.metadata-missing-file'], (
            'the link is not followed, but it leads to docs/feat/, which docs/ lists in its own right'
        )

    def test_run_skills_with_a_skill_breaking_every_metadata_rule_reports_each_in_order(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/code/a.md')
        _write(tmp_path, 'docs/feat/a.md')
        _write_skill(
            tmp_path, '  references: docs/code/a.md docs/feat/a.md docs/feat/absent.md\n  scripts: src/tool.py\n'
        )
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [finding.rule for finding in run.findings()] == [
            'skill.metadata-duplicate-name',
            'skill.metadata-missing-file',
            'skill.metadata-outside-scope',
        ], 'each subkey is checked whole, references before scripts'


# The frontmatter of a clean skill named `review`, ending on line 4, so the body starts on line 5.
_REVIEW_FRONTMATTER: Final[bytes] = b'---\nname: review\ndescription: Review a change\n---\n'


@pytest.mark.it
class TestRunSkillsResources:
    def test_run_skills_with_escaping_links_reports_each_in_its_file_ordered_by_file_then_line(
        self, tmp_path: Path
    ) -> None:
        #: Given
        skill = '.agents/skills/review'
        _write(
            tmp_path, f'{skill}/SKILL.md', _REVIEW_FRONTMATTER + b'# Review\n\nRead [the guide](../../docs/guide.md).\n'
        )
        _write(tmp_path, f'{skill}/references/deep/guide.md', b'# Guide\n\nBack to [the skill](../SKILL.md).\n')
        _write(tmp_path, f'{skill}/references/a.md', b'[up](../a.md)\n\n[in](SKILL.md) and ![flow](../../flow.png)\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse(f'{skill}/SKILL.md'),
                line=LineNumber(7),
                rule='skill.link-escapes',
                message='`../../docs/guide.md` leaves the skill directory',
                notes=(Note(NoteKind.HELP, 'link a file inside the skill, relative to the skill root'),),
            ),
            Finding(
                path=RootRelativePath.parse(f'{skill}/references/a.md'),
                line=LineNumber(1),
                rule='skill.link-escapes',
                message='`../a.md` leaves the skill directory',
                notes=(Note(NoteKind.HELP, 'link a file inside the skill, relative to the skill root'),),
            ),
            Finding(
                path=RootRelativePath.parse(f'{skill}/references/a.md'),
                line=LineNumber(3),
                rule='skill.link-escapes',
                message='`../../flow.png` leaves the skill directory',
                notes=(Note(NoteKind.HELP, 'link a file inside the skill, relative to the skill root'),),
            ),
            Finding(
                path=RootRelativePath.parse(f'{skill}/references/deep/guide.md'),
                line=LineNumber(3),
                rule='skill.link-escapes',
                message='`../SKILL.md` leaves the skill directory',
                notes=(Note(NoteKind.HELP, 'link a file inside the skill, relative to the skill root'),),
            ),
        ), 'the SKILL.md first, then each resource by path, each read from the skill root and located in its own file'

    def test_run_skills_with_an_escaping_link_in_a_linked_skill_reports_it_where_the_agent_finds_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'skills/review/SKILL.md', _REVIEW_FRONTMATTER)
        _write(tmp_path, 'skills/review/references/a.md', b'See [the skill](../SKILL.md).\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/review/references/a.md'),
                line=LineNumber(1),
                rule='skill.link-escapes',
                message='`../SKILL.md` leaves the skill directory',
                notes=(Note(NoteKind.HELP, 'link a file inside the skill, relative to the skill root'),),
            ),
        ), 'the resource is read through the linked entry, and the finding names it under the skills directory'

    def test_run_skills_with_an_undecodable_resource_reports_only_that_it_is_undecodable(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md', _REVIEW_FRONTMATTER)
        _write(tmp_path, '.agents/skills/review/references/latin.md', b'# Caf\xe9\n\n[up](../../outside.md)\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/review/references/latin.md'),
                line=LineNumber(1),
                rule='skill.undecodable',
                message='resource is not valid UTF-8',
            ),
        ), 'a resource that is not UTF-8 is reported once, at the resource, and its links are never checked'

    def test_run_skills_with_an_undecodable_skill_md_still_checks_its_resources(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md', b'---\nname: caf\xe9\n---\n')
        _write(tmp_path, '.agents/skills/review/references/a.md', b'[up](../a.md)\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/review/SKILL.md'),
                line=LineNumber(1),
                rule='skill.undecodable',
                message='SKILL.md is not valid UTF-8',
            ),
            Finding(
                path=RootRelativePath.parse('.agents/skills/review/references/a.md'),
                line=LineNumber(1),
                rule='skill.link-escapes',
                message='`../a.md` leaves the skill directory',
                notes=(Note(NoteKind.HELP, 'link a file inside the skill, relative to the skill root'),),
            ),
        ), 'each resource is a file of its own, checked whatever bytes the SKILL.md holds'

    def test_run_skills_with_absolute_fragment_and_url_links_in_a_resource_reports_all_but_the_url(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md', _REVIEW_FRONTMATTER)
        _write(
            tmp_path,
            '.agents/skills/review/references/a.md',
            b'# A\n\n[a](/x.md) [b](#nothing) [c](https://example.com) [d](#a)\n',
        )
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/review/references/a.md'),
                line=LineNumber(3),
                rule='skill.link-absolute',
                message='`/x.md` is absolute',
                notes=(Note(NoteKind.HELP, 'link relative to the skill root'),),
            ),
            Finding(
                path=RootRelativePath.parse('.agents/skills/review/references/a.md'),
                line=LineNumber(3),
                rule='skill.link-fragment',
                message='`#nothing` names a heading this file does not have',
            ),
        ), (
            'a resource is held to the absolute and fragment rules as the SKILL.md is, a URL names no path, and a '
            'fragment naming its own heading is not reported'
        )

    def test_run_skills_with_absolute_and_dangling_fragment_links_in_a_nested_resource_reports_them_there(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'skills/review/SKILL.md', _REVIEW_FRONTMATTER + b'# Review\n\n## Usage\n')
        _write(
            tmp_path,
            'skills/review/references/deep/guide.md',
            b'# Guide\n\nSee [the guide](#guide), [the usage](#usage) and ![the flow](/assets/flow.png).\n',
        )
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/review/references/deep/guide.md'),
                line=LineNumber(3),
                rule='skill.link-fragment',
                message='`#usage` names a heading this file does not have',
            ),
            Finding(
                path=RootRelativePath.parse('.agents/skills/review/references/deep/guide.md'),
                line=LineNumber(3),
                rule='skill.link-absolute',
                message='`/assets/flow.png` is absolute',
                notes=(Note(NoteKind.HELP, 'link relative to the skill root'),),
            ),
        ), (
            "a fragment names the resource's own headings, not the SKILL.md's, and each finding names the resource "
            'where the agent reads it, under the skills directory'
        )

    def test_run_skills_with_an_absolute_link_in_a_resource_reached_through_two_links_reports_it_once(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'skills/review/SKILL.md', _REVIEW_FRONTMATTER)
        _write(tmp_path, 'skills/review/references/guide.md', b'# Guide\n\nRead [the docs](/docs/guide.md).\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/review/references/guide.md'),
                line=LineNumber(3),
                rule='skill.link-absolute',
                message='`/docs/guide.md` is absolute',
                notes=(Note(NoteKind.HELP, 'link relative to the skill root'),),
            ),
        ), 'a skill reached through the skills-directory link and its own entry link is one skill, reported once'

    def test_run_skills_with_a_link_to_a_file_metadata_links_in_reports_nothing(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/code/logging.md')
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            b'---\nname: review\ndescription: Review a change\nmetadata:\n  references: docs/code/logging.md\n---\n'
            b'See [logging](references/logging.md).\n',
        )
        _write(tmp_path, '.agents/skills/review/references/deep/x.md', b'See [logging](references/logging.md).\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (), (
            'a file metadata links in is named from the skill root, even in a nested resource, so no link to it escapes'
        )


def _broken(path: str, line: int, url: str) -> Finding:
    """The `skill.link-broken` finding of a link, located in its file.

    Args:
        path: The file holding the link, as an agent reaches it, relative to the root.
        line: The line the link is on.
        url: The link's destination, decoded, as the message shows it.
    """
    return Finding(
        path=RootRelativePath.parse(path),
        line=LineNumber(line),
        rule='skill.link-broken',
        message=f'`{url}` names nothing in the skill',
        notes=(Note(NoteKind.HELP, 'link a file or a directory the skill holds, relative to the skill root'),),
    )


@pytest.mark.it
class TestRunSkillsBrokenLinks:
    def test_run_skills_with_a_broken_link_in_skill_md_reports_only_it(self, tmp_path: Path) -> None:
        #: Given
        skill = '.agents/skills/review'
        _write(
            tmp_path,
            f'{skill}/SKILL.md',
            _REVIEW_FRONTMATTER + b'# Review\n\nRun [the script](scripts/run.py) from [scripts](scripts/).\n\n'
            b'Read [the steps](references/steps.md).\n',
        )
        _write(tmp_path, f'{skill}/scripts/run.py')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (_broken(f'{skill}/SKILL.md', 9, 'references/steps.md'),), (
            'a file and a directory the skill holds resolve, whatever their kind, and the missing file does not'
        )

    def test_run_skills_with_a_broken_link_in_a_nested_resource_reports_it_there(self, tmp_path: Path) -> None:
        #: Given
        skill = '.agents/skills/review'
        _write(tmp_path, f'{skill}/SKILL.md', _REVIEW_FRONTMATTER)
        _write(tmp_path, f'{skill}/references/a.md', b'# A\n')
        _write(
            tmp_path,
            f'{skill}/references/deep/guide.md',
            b'# Guide\n\nSee [a](references/a.md), not [a](a.md) or [itself](guide.md).\n',
        )
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            _broken(f'{skill}/references/deep/guide.md', 3, 'a.md'),
            _broken(f'{skill}/references/deep/guide.md', 3, 'guide.md'),
        ), 'a link in a resource is read from the skill root, not from the resource, so only the first resolves'

    def test_run_skills_with_a_link_through_a_symlinked_directory_in_the_skill_resolves_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        skill = '.agents/skills/review'
        _write(
            tmp_path,
            f'{skill}/SKILL.md',
            _REVIEW_FRONTMATTER + b'# Review\n\nSee [d](guides/d.md) and [e](guides/e.md).\n',
        )
        _write(tmp_path, 'shared/guides/d.md', b'# D\n')
        (tmp_path / '.agents' / 'skills' / 'review' / 'guides').symlink_to('../../../shared/guides')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (_broken(f'{skill}/SKILL.md', 7, 'guides/e.md'),), (
            'the symlink inside the skill is followed to the files it leads to, and a file it lacks is missing'
        )

    def test_run_skills_with_a_broken_link_in_a_linked_skill_reports_it_where_the_agent_finds_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(
            tmp_path,
            'skills/review/SKILL.md',
            _REVIEW_FRONTMATTER + b'# Review\n\nSee [a](references/a.md) and [b](references/b.md).\n',
        )
        _write(tmp_path, 'skills/review/references/a.md', b'# A\n\nBack to [the skill](SKILL.md), on to [c](c.md).\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            _broken('.agents/skills/review/SKILL.md', 7, 'references/b.md'),
            _broken('.agents/skills/review/references/a.md', 3, 'c.md'),
        ), 'each finding names its file where an agent reaches it, under the skills directory, not under skills/'

    def test_run_skills_with_a_link_to_a_missing_file_metadata_lists_reports_only_the_missing_file(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(
            tmp_path,
            '.agents/skills/review/SKILL.md',
            b'---\nname: review\ndescription: Review a change\nmetadata:\n  references: docs/feat/absent.md\n---\n'
            b'See [absent](references/absent.md).\n',
        )
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [(str(finding.path), finding.line.value, finding.rule) for finding in run.findings()] == [
            ('.agents/skills/review/SKILL.md', 4, 'skill.metadata-missing-file'),
        ], 'the listed file that is missing is reported once, by the metadata rule, and the link to it is not broken'

    def test_run_skills_with_escaping_links_reports_them_escaping_and_never_broken(self, tmp_path: Path) -> None:
        #: Given
        skill = '.agents/skills/review'
        _write(
            tmp_path,
            f'{skill}/SKILL.md',
            _REVIEW_FRONTMATTER + b'# Review\n\nSee [back in](../review/references/a.md) and [out](../gone.md).\n',
        )
        _write(tmp_path, f'{skill}/references/a.md', b'# A\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [(finding.line.value, finding.rule) for finding in run.findings()] == [
            (7, 'skill.link-escapes'),
            (7, 'skill.link-escapes'),
        ], 'a link above the skill root is the escape rule alone, whether a file lies where it leads or not'

    def test_run_skills_with_unparseable_frontmatter_judges_no_link_broken_but_reports_an_escape(
        self, tmp_path: Path
    ) -> None:
        #: Given
        # the YAML does not parse, so the `references` it means to list cannot be read
        skill = '.agents/skills/review'
        _write(
            tmp_path,
            f'{skill}/SKILL.md',
            b'---\nname: review\nmetadata: {references: docs/code/logging.md\n---\n'
            b'See [logging](references/logging.md) and [gone](references/gone.md).\n',
        )
        _write(
            tmp_path, f'{skill}/references/a.md', b'[logging](references/logging.md) [gone](gone.md) [out](../x.md)\n'
        )
        _write(tmp_path, 'docs/code/logging.md')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [(str(finding.path), finding.rule) for finding in run.findings()] == [
            (f'{skill}/SKILL.md', 'skill.frontmatter-unparseable'),
            (f'{skill}/references/a.md', 'skill.link-escapes'),
        ], 'with metadata unknown no link is judged broken, in the SKILL.md or a resource, and the escape still is'

    def test_run_skills_with_an_undecodable_skill_md_judges_no_resource_link_broken_but_reports_an_escape(
        self, tmp_path: Path
    ) -> None:
        #: Given
        skill = '.agents/skills/review'
        _write(
            tmp_path,
            f'{skill}/SKILL.md',
            b'---\nname: caf\xe9\nmetadata:\n  references: docs/code/logging.md\n---\n',
        )
        _write(
            tmp_path, f'{skill}/references/a.md', b'[logging](references/logging.md) [gone](gone.md) [out](../x.md)\n'
        )
        _write(tmp_path, 'docs/code/logging.md')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [(str(finding.path), finding.rule) for finding in run.findings()] == [
            (f'{skill}/SKILL.md', 'skill.undecodable'),
            (f'{skill}/references/a.md', 'skill.link-escapes'),
        ], 'a SKILL.md that is not UTF-8 hides its metadata, so no resource link is judged broken, and the escape is'


def _skill_md_of(line_count: int) -> bytes:
    """A clean `SKILL.md` for the skill `review` of exactly `line_count` lines, frontmatter included.

    Args:
        line_count: The lines in the whole file, the four of `_REVIEW_FRONTMATTER` among them; at least 4.
    """
    return _REVIEW_FRONTMATTER + b'Body.\n' * (line_count - 4)


@pytest.mark.it
class TestRunSkillsLineBudget:
    def test_run_skills_with_a_skill_md_over_500_lines_reports_it_on_line_1_with_help(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md', _skill_md_of(501))
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/review/SKILL.md'),
                line=LineNumber(1),
                rule='skill.lines-budget',
                message='501 lines; the budget is 500',
                notes=(
                    Note(
                        NoteKind.HELP,
                        'move detail most activations do not need into files under references/, and say in SKILL.md '
                        'when to read each',
                    ),
                ),
            ),
        ), 'a SKILL.md one line over the budget, its frontmatter counted, is reported once, on line 1'

    def test_run_skills_with_a_long_skill_md_in_a_linked_skill_reports_it_where_the_agent_finds_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'skills/review/SKILL.md', _skill_md_of(501))
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review').symlink_to('../../skills/review')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [(str(finding.path), finding.line.value, finding.rule) for finding in run.findings()] == [
            ('.agents/skills/review/SKILL.md', 1, 'skill.lines-budget'),
        ], 'the SKILL.md is counted where the link leads, and reported under the skills directory, not under skills/'

    def test_run_skills_with_a_skill_md_of_500_lines_reports_nothing(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md', _skill_md_of(500))
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (), 'a SKILL.md of exactly 500 lines, its frontmatter counted, is within the budget'

    def test_run_skills_with_a_resource_over_500_lines_reports_nothing(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md', _REVIEW_FRONTMATTER)
        _write(tmp_path, '.agents/skills/review/references/guide.md', b'Detail.\n' * 600)
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (), 'the budget holds the SKILL.md alone, so a long resource is never reported'

    def test_run_skills_with_a_long_misnamed_skill_md_reports_the_budget_after_the_frontmatter_before_links(
        self, tmp_path: Path
    ) -> None:
        #: Given
        frontmatter = b'---\nname: audit\ndescription: Review a change\n---\n'
        body = b'See [the steps](references/steps.md).\n' + b'Body.\n' * 497
        _write(tmp_path, '.agents/skills/review/SKILL.md', frontmatter + body)
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert [(finding.line.value, finding.rule) for finding in run.findings()] == [
            (2, 'skill.name-matches-directory'),
            (1, 'skill.lines-budget'),
            (5, 'skill.link-broken'),
        ], 'the SKILL.md findings follow the check order, frontmatter then the budget then links, not the line order'


_RENAMING_LINK_NOTES: Final[tuple[Note, ...]] = (Note(NoteKind.NOTE, "'bar' is a link to 'skills/foo'"),)
"""The notes of a `skill.name-matches-directory` finding on the link `bar -> skills/foo`."""


def _write_renaming_link(root: Path, name: str) -> None:
    """Write the skill `skills/foo` named `name`, and link it into the skills directory as `.agents/skills/bar`.

    Args:
        root: Directory the tree is written under, as the repository root.
        name: The `name` the skill's frontmatter states.
    """
    _write(root, 'skills/foo/SKILL.md', f'---\nname: {name}\ndescription: Review a change\n---\n'.encode())
    (root / '.agents' / 'skills').mkdir(parents=True)
    (root / '.agents' / 'skills' / 'bar').symlink_to('../../skills/foo')


@pytest.mark.it
class TestRunSkillsNameMatchesDirectory:
    def test_run_skills_with_a_renaming_link_and_the_listed_name_reports_nothing(self, tmp_path: Path) -> None:
        #: Given
        _write_renaming_link(tmp_path, name='bar')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (), 'the name is held to the entry an agent lists the skill by'

    def test_run_skills_with_a_renaming_link_and_the_name_it_leads_to_reports_the_listed_name(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write_renaming_link(tmp_path, name='foo')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/bar/SKILL.md'),
                line=LineNumber(2),
                rule='skill.name-matches-directory',
                message="`name` is 'foo'; expected 'bar', the name of the skill directory",
                notes=_RENAMING_LINK_NOTES,
            ),
        ), 'where the link leads plays no part: a name matching it alone is held to the listed name'

    def test_run_skills_with_a_renaming_link_through_a_linked_skills_directory_reports_it_once(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write_renaming_link(tmp_path, name='foo')
        (tmp_path / '.claude').mkdir()
        (tmp_path / '.claude' / 'skills').symlink_to('../.agents/skills')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/bar/SKILL.md'),
                line=LineNumber(2),
                rule='skill.name-matches-directory',
                message="`name` is 'foo'; expected 'bar', the name of the skill directory",
                notes=_RENAMING_LINK_NOTES,
            ),
        ), 'a skill two agents reach, one through a linked skills directory, is one skill, held to its listed name'

    def test_run_skills_with_a_renaming_link_inside_a_linked_skills_directory_reports_the_listed_name(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'skills/foo/SKILL.md', b'---\nname: foo\ndescription: Review a change\n---\n')
        (tmp_path / 'agent-skills').mkdir()
        (tmp_path / 'agent-skills' / 'bar').symlink_to('../skills/foo')
        (tmp_path / '.agents').mkdir()
        (tmp_path / '.agents' / 'skills').symlink_to('../agent-skills')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        # The model names a skill under the resolved skills directory, so `agent-skills/bar` is its ref, and every
        # finding about it is reported there, this one among them.
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('agent-skills/bar/SKILL.md'),
                line=LineNumber(2),
                rule='skill.name-matches-directory',
                message="`name` is 'foo'; expected 'bar', the name of the skill directory",
                notes=_RENAMING_LINK_NOTES,
            ),
        ), 'through a linked skills directory and a linked entry, the name is held to the entry listed'

    def test_run_skills_with_a_linked_skill_md_holds_the_name_to_the_listed_directory(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'shared/text/SKILL.md', b'---\nname: review\ndescription: Review a change\n---\n')
        (tmp_path / '.agents' / 'skills' / 'review').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'review' / 'SKILL.md').symlink_to('../../../shared/text/SKILL.md')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (), 'the listed directory names the skill, not the directory its SKILL.md leads to'

    def test_run_skills_with_an_entry_leading_to_the_root_holds_the_name_to_the_listed_entry(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'SKILL.md', b'---\nname: x\ndescription: Review a change\n---\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'x').symlink_to('../..')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (), 'an entry leading to the root is compared with its listed name, like any other'

    def test_run_skills_with_a_misnamed_entry_leading_to_the_root_reports_the_listed_entry_with_a_root_note(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'SKILL.md', b'---\nname: review\ndescription: Review a change\n---\n')
        (tmp_path / '.agents' / 'skills').mkdir(parents=True)
        (tmp_path / '.agents' / 'skills' / 'x').symlink_to('../..')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/x/SKILL.md'),
                line=LineNumber(2),
                rule='skill.name-matches-directory',
                message="`name` is 'review'; expected 'x', the name of the skill directory",
                notes=(Note(NoteKind.NOTE, "'x' is a link to the repository root"),),
            ),
        ), 'an entry leading to the root is held to its listed name, and the note names the root as such'

    def test_run_skills_with_a_misnamed_regular_skill_reports_the_skill_directory(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, '.agents/skills/review/SKILL.md', b'---\nname: audit\ndescription: Review a change\n---\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            Finding(
                path=RootRelativePath.parse('.agents/skills/review/SKILL.md'),
                line=LineNumber(2),
                rule='skill.name-matches-directory',
                message="`name` is 'audit'; expected 'review', the name of the skill directory",
            ),
        ), 'a name that differs from the skill directory is the one finding'


_CLEAN_SKILL_MD: Final[bytes] = b'---\nname: review\ndescription: Review a change\n---\n'
"""A `SKILL.md` the skill `review` passes every other rule with."""


def _outside_finding(path: str, link: str, target: Path | str) -> Finding:
    """The `skill.symlink-outside` finding at `path`, whose chain leaves the repository at `link -> target`.

    Args:
        path: Where an agent reaches the symlink, root-relative.
        link: The link the chain leaves the repository through, root-relative.
        target: That link's target, as the scan read it.
    """
    return Finding(
        path=RootRelativePath.parse(path),
        line=LineNumber(1),
        rule='skill.symlink-outside',
        message='symlink leads outside the repository',
        notes=(
            Note(NoteKind.NOTE, f'leaves the repository at {link} -> {target}'),
            Note(NoteKind.HELP, 'keep every file a skill loads inside the repository'),
        ),
    )


@pytest.fixture(scope='function')
def repository_beside_elsewhere(tmp_path: Path) -> Path:
    """An empty repository root, `tmp_path/repository`, beside `tmp_path/elsewhere`, a directory outside it.

    `elsewhere` holds a conforming skill, `x`, and a Markdown file, `x.md`, for a link to lead to.

    Args:
        tmp_path: Directory the repository and the directory outside it are written into.

    Returns:
        The repository root.
    """
    _write(tmp_path, 'elsewhere/x/SKILL.md', b'---\nname: x\ndescription: Kept outside\n---\n')
    _write(tmp_path, 'elsewhere/x.md', _CLEAN_SKILL_MD)
    root = tmp_path / 'repository'
    root.mkdir()
    return root


@pytest.mark.it
class TestRunSkillsSymlinkOutside:
    def test_run_skills_with_a_skills_directory_linked_outside_reports_it_at_the_skills_directory(
        self, repository_beside_elsewhere: Path
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        elsewhere = root.parent / 'elsewhere'
        (root / '.claude').mkdir()
        (root / '.claude' / 'skills').symlink_to(elsewhere)
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (_outside_finding('.claude/skills', '.claude/skills', elsewhere),), (
            'an agent would load its skills from outside the repository, so the skills directory is reported'
        )

    def test_run_skills_with_a_skill_entry_linked_outside_reports_it_at_the_entry(
        self, repository_beside_elsewhere: Path
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        target = root.parent / 'elsewhere' / 'x'
        (root / '.agents' / 'skills').mkdir(parents=True)
        (root / '.agents' / 'skills' / 'x').symlink_to(target)
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (_outside_finding('.agents/skills/x', '.agents/skills/x', target),), (
            'the entry an agent lists is reported where it is listed'
        )

    def test_run_skills_with_a_skill_entry_linked_outside_checks_no_skill(
        self, repository_beside_elsewhere: Path
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        (root / '.agents' / 'skills').mkdir(parents=True)
        (root / '.agents' / 'skills' / 'x').symlink_to(root.parent / 'elsewhere' / 'x')
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.reports == (), 'the entry is no skill, so no other rule judges what lies behind it'

    def test_run_skills_with_a_skill_file_linked_outside_reports_it_at_the_skill_file(
        self, repository_beside_elsewhere: Path
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        target = root.parent / 'elsewhere' / 'x.md'
        (root / '.agents' / 'skills' / 'review').mkdir(parents=True)
        (root / '.agents' / 'skills' / 'review' / 'SKILL.md').symlink_to(target)
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            _outside_finding('.agents/skills/review/SKILL.md', '.agents/skills/review/SKILL.md', target),
        ), 'the SKILL.md an agent would read from outside the repository is reported, and nothing else'

    def test_run_skills_with_a_directory_inside_a_skill_linked_outside_reports_it_where_the_agent_reaches_it(
        self, repository_beside_elsewhere: Path
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        target = root.parent / 'elsewhere' / 'x'
        _write(root, '.agents/skills/review/SKILL.md', _CLEAN_SKILL_MD)
        (root / '.agents' / 'skills' / 'review' / 'references').symlink_to(target)
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            _outside_finding('.agents/skills/review/references', '.agents/skills/review/references', target),
        ), 'a directory of the skill linked from outside is reported, and nothing behind it is read'

    def test_run_skills_with_a_chain_inside_the_repository_that_leaves_it_reports_the_link_it_leaves_through(
        self, repository_beside_elsewhere: Path
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        elsewhere = root.parent / 'elsewhere'
        (root / '.agents' / 'skills').mkdir(parents=True)
        (root / '.agents' / 'skills' / 'x').symlink_to('../../hop/x')
        (root / 'hop').symlink_to(elsewhere)
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (_outside_finding('.agents/skills/x', 'hop', elsewhere),), (
            'the finding is at the entry an agent lists, and its note names the link the chain leaves through'
        )

    def test_run_skills_with_a_link_climbing_above_the_repository_reports_it(
        self, repository_beside_elsewhere: Path
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        _write(root, '.agents/skills/review/SKILL.md', _CLEAN_SKILL_MD)
        (root / '.agents' / 'skills' / 'review' / 'shared').symlink_to('../../../../elsewhere/x')
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (
            _outside_finding('.agents/skills/review/shared', '.agents/skills/review/shared', '../../../../elsewhere/x'),
        ), 'a `..` climbing above the root leaves the repository as an absolute target does'

    def test_run_skills_with_a_link_dangling_inside_the_repository_reports_nothing(
        self, repository_beside_elsewhere: Path
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        _write(root, '.agents/skills/review/SKILL.md', _CLEAN_SKILL_MD)
        (root / '.agents' / 'skills' / 'gone').symlink_to('../../skills/gone')
        (root / '.agents' / 'skills' / 'review' / 'references').symlink_to('../../../missing')
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (), 'a link dangling inside the repository is not one leading outside it'

    def test_run_skills_with_a_skills_directory_linked_inside_the_repository_reports_nothing(
        self, repository_beside_elsewhere: Path
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        _write(root, '.agents/skills/review/SKILL.md', _CLEAN_SKILL_MD)
        (root / '.claude').mkdir()
        (root / '.claude' / 'skills').symlink_to('../.agents/skills')
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_skill(database)

        #: Then
        assert run.findings() == (), 'a skills directory linked to another inside the repository is self-contained'


@pytest.mark.it
class TestRunSkillsSkillFile:
    def test_run_skills_with_the_skill_file_alone_reports_no_resource(self, tmp_path: Path) -> None:
        #: Given
        skill = '.agents/skills/review'
        _write(tmp_path, f'{skill}/SKILL.md', _REVIEW_FRONTMATTER + b'# Review\n\nSee [/x.md](/x.md).\n')
        _write(tmp_path, f'{skill}/references/a.md', b'# A\n\nSee [/y.md](/y.md).\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))
        selection = SkillSelection(SkillRef(RootRelativePath.parse(skill)), SkillScope.SKILL_FILE)

        #: When
        run = run_skills(database, (selection,))

        #: Then
        assert run.reports == (
            SkillReport(
                selection.ref,
                violations=(
                    Violation(
                        line=LineNumber(7),
                        rule='skill.link-absolute',
                        message='`/x.md` is absolute',
                        notes=(Note(NoteKind.HELP, 'link relative to the skill root'),),
                    ),
                ),
                resources=(),
                symlinks=(),
            ),
        ), 'the SKILL.md is checked and no resource is read or reported'

    def test_run_skills_with_the_skill_file_alone_judges_a_link_to_a_resource_present(self, tmp_path: Path) -> None:
        #: Given
        skill = '.agents/skills/review'
        _write(
            tmp_path,
            f'{skill}/SKILL.md',
            _REVIEW_FRONTMATTER + b'# Review\n\nSee [a](references/a.md) and [b](references/b.md).\n',
        )
        _write(tmp_path, f'{skill}/references/a.md', b'# A\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))
        selection = SkillSelection(SkillRef(RootRelativePath.parse(skill)), SkillScope.SKILL_FILE)

        #: When
        run = run_skills(database, (selection,))

        #: Then
        assert run.findings() == (_broken(f'{skill}/SKILL.md', 7, 'references/b.md'),), (
            'a link to a resource still resolves against the skill, and only the one naming nothing is broken'
        )

    def test_run_skills_with_the_skill_file_alone_reports_the_layout_but_no_link_inside_the_skill(
        self, repository_beside_elsewhere: Path
    ) -> None:
        #: Given
        root = repository_beside_elsewhere
        target = root.parent / 'elsewhere' / 'x'
        skill = '.agents/skills/review'
        _write(root, f'{skill}/SKILL.md', _CLEAN_SKILL_MD)
        (root / skill / 'references').symlink_to(target)
        (root / '.agents' / 'skills' / 'x').symlink_to(target)
        database = Database(take_snapshot(root, SNAPSHOT_SCOPE))
        selection = SkillSelection(SkillRef(RootRelativePath.parse(skill)), SkillScope.SKILL_FILE)

        #: When
        run = run_skills(database, (selection,))

        #: Then
        assert run.findings() == (_outside_finding('.agents/skills/x', '.agents/skills/x', target),), (
            'the skills directory an agent lists is still judged, but no link inside a skill checked by its SKILL.md'
        )
