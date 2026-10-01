"""The frontmatter run over a database opened on a snapshot of a real tree.

``run_frontmatter`` reads everything through the database, and the database answers from one snapshot, so the run
reports the tree as the scan saw it: every kind of report, and nothing written to the disk afterwards.
"""

import sys
from pathlib import Path
from textwrap import dedent
from typing import Final

import pytest

from lorecraft.checks import CheckRun, Database, Violation, run_frontmatter
from lorecraft.core.path import RootRelativePath
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.project.syntax import LineNumber
from lorecraft.vfs import take_snapshot

# A frontmatter schema requiring a string ``description``, so a document without one yields a schema finding.
DESCRIPTION_STRUCTURE_SPEC: Final[str] = dedent(
    """
    {
      "frontmatter": {
        "type": "object",
        "required": ["description"],
        "properties": {"description": {"type": "string"}}
      }
    }
    """
)

# A structure rule and no frontmatter schema, so a corpus governed by it is ungoverned for frontmatter.
NO_FRONTMATTER_STRUCTURE_SPEC: Final[str] = '{"empty_sections": "forbidden"}'


def _write(root: Path, relative: str, data: bytes = b'') -> Path:
    """Write one file under the root, creating its parents, and return its path.

    Args:
        root: Directory the file is written under.
        relative: Slash-separated path of the file, relative to `root`.
        data: Bytes the file holds. The file is empty when omitted.
    """
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _run_every_document(database: Database) -> CheckRun:
    """Check every document the database's model lists.

    Args:
        database: Snapshot database whose model supplies the documents and whose files the check reads.
    """
    return run_frontmatter(database, database.model().documents())


@pytest.fixture(scope='function')
def lorecraft_tree(tmp_path: Path) -> Path:
    """A tree shaped like this repository, built to produce every kind of report.

    Corpus `code` is governed: one clean document, one misnamed, one without a description, one without
    frontmatter and one that is not UTF-8, plus a nested document the loader never lists. Corpus `feat`
    has a structure specification but no frontmatter schema in it, so its document is ungoverned. Beside them
    sits a loose file under `docs/`.

    Args:
        tmp_path: Directory the specifications and documents are written into, as the repository root.
    """
    _write(tmp_path, 'docs/__meta__/code.md', b'# Code\n')
    _write(tmp_path, 'docs/__meta__/code.structure.json', DESCRIPTION_STRUCTURE_SPEC.encode())
    _write(tmp_path, 'docs/__meta__/feat.md', b'# Feat\n')
    _write(tmp_path, 'docs/__meta__/feat.structure.json', NO_FRONTMATTER_STRUCTURE_SPEC.encode())
    _write(tmp_path, 'docs/code/clean.md', b'---\nname: "clean"\ndescription: "A clean document"\n---\n')
    _write(tmp_path, 'docs/code/misnamed.md', b'---\nname: "other"\ndescription: "Named wrong"\n---\n')
    _write(tmp_path, 'docs/code/undescribed.md', b'---\nname: "undescribed"\n---\n')
    _write(tmp_path, 'docs/code/bare.md', b'# No frontmatter\n')
    _write(tmp_path, 'docs/code/latin.md', b'---\nname: "caf\xe9"\n---\n')
    _write(tmp_path, 'docs/code/sub/deep.md', b'# Nested\n')
    _write(tmp_path, 'docs/feat/overview.md', b'---\nname: "overview"\n---\n')
    _write(tmp_path, 'docs/glossary.md', b'# Glossary\n')
    return tmp_path


@pytest.mark.it
class TestRunFrontmatter:
    def test_run_frontmatter_over_a_snapshot_reports_one_rule_per_broken_document(self, lorecraft_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(lorecraft_tree, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_document(database)

        #: Then
        rules = sorted((str(finding.path), finding.rule) for finding in run.findings())
        assert rules == [
            ('docs/code/bare.md', 'frontmatter.missing'),
            ('docs/code/latin.md', 'frontmatter.undecodable'),
            ('docs/code/misnamed.md', 'frontmatter.name-matches-filename'),
            ('docs/code/undescribed.md', 'code.description'),
        ], 'each broken document yields exactly the finding its defect names'

    def test_run_frontmatter_over_a_snapshot_reports_a_corpus_without_a_frontmatter_schema_as_ungoverned(
        self, lorecraft_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(lorecraft_tree, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_document(database)

        #: Then
        ungoverned = [report.ref.path for report in run.reports if not report.governed]
        assert ungoverned == [RootRelativePath.parse('docs/feat/overview.md')], (
            'the feat structure specification states no frontmatter schema, so its one document is ungoverned'
        )

    def test_run_frontmatter_after_the_disk_changes_reports_the_tree_the_snapshot_saw(
        self, lorecraft_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(lorecraft_tree, SNAPSHOT_SCOPE))
        _write(lorecraft_tree, 'docs/code/bare.md', b'---\nname: "bare"\ndescription: "Fixed after the scan"\n---\n')

        #: When
        run = _run_every_document(database)

        #: Then
        bare_rules = [finding.rule for finding in run.findings() if str(finding.path) == 'docs/code/bare.md']
        assert bare_rules == ['frontmatter.missing'], (
            'the run reads the document as the scan saw it, not as it was rewritten afterwards'
        )

    def test_run_frontmatter_with_the_wrong_name_written_last_reports_it_and_the_repetition_on_that_line(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.md', b'# Code\n')
        _write(tmp_path, 'docs/__meta__/code.structure.json', DESCRIPTION_STRUCTURE_SPEC.encode())
        _write(tmp_path, 'docs/code/guide.md', b'---\nname: "guide"\ndescription: "A guide"\nname: "other"\n---\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_document(database)

        #: Then
        assert [report.violations for report in run.reports] == [
            (
                Violation(
                    line=LineNumber(4),
                    rule='frontmatter.name-matches-filename',
                    message="`name` is 'other'; expected 'guide', the document's filename",
                ),
                Violation(
                    line=LineNumber(4),
                    rule='frontmatter.duplicate-key',
                    message="'name' is already written on line 2",
                ),
            )
        ], 'the name the decoder kept is judged on the last line it is written on, beside the repetition'

    def test_run_frontmatter_with_the_right_name_written_last_reports_only_the_repetition(self, tmp_path: Path) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.md', b'# Code\n')
        _write(tmp_path, 'docs/__meta__/code.structure.json', DESCRIPTION_STRUCTURE_SPEC.encode())
        _write(tmp_path, 'docs/code/guide.md', b'---\nname: "other"\ndescription: "A guide"\nname: "guide"\n---\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_document(database)

        #: Then
        assert [report.violations for report in run.reports] == [
            (
                Violation(
                    line=LineNumber(4),
                    rule='frontmatter.duplicate-key',
                    message="'name' is already written on line 2",
                ),
            )
        ], 'the decoder kept the right name, so the overwritten wrong one is reported only as a repetition'

    def test_run_frontmatter_with_a_scalar_its_tag_cannot_construct_reports_it_and_checks_the_rest(
        self, tmp_path: Path
    ) -> None:
        #: Given
        _write(tmp_path, 'docs/__meta__/code.md', b'# Code\n')
        _write(tmp_path, 'docs/__meta__/code.structure.json', DESCRIPTION_STRUCTURE_SPEC.encode())
        _write(tmp_path, 'docs/code/clean.md', b'---\nname: "clean"\ndescription: "A clean document"\n---\n')
        _write(tmp_path, 'docs/code/guide.md', b'---\nname: "guide"\ndescription: !!int many\n---\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_document(database)

        #: Then
        assert [report.violations for report in run.reports] == [
            (),
            (
                Violation(
                    line=LineNumber(3),
                    rule='frontmatter.unparseable',
                    message=(
                        "frontmatter is not valid YAML: could not construct a value for the tag 'tag:yaml.org,2002:int'"
                    ),
                ),
            ),
        ], 'the scalar is one finding on its line, and the run goes on to check the other document'

    def test_run_frontmatter_with_collections_nested_too_deeply_reports_it_and_checks_the_rest(
        self, tmp_path: Path
    ) -> None:
        #: Given
        # the composer spends at least one frame per level, so as many levels as the recursion limit always
        # exhaust the stack, whatever the limit is
        depth = sys.getrecursionlimit()
        nested = f'---\nname: "guide"\ndescription: {"[" * depth}{"]" * depth}\n---\n'
        _write(tmp_path, 'docs/__meta__/code.md', b'# Code\n')
        _write(tmp_path, 'docs/__meta__/code.structure.json', DESCRIPTION_STRUCTURE_SPEC.encode())
        _write(tmp_path, 'docs/code/clean.md', b'---\nname: "clean"\ndescription: "A clean document"\n---\n')
        _write(tmp_path, 'docs/code/guide.md', nested.encode())
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_document(database)

        #: Then
        assert [report.violations for report in run.reports] == [
            (),
            (
                Violation(
                    line=LineNumber(1),
                    rule='frontmatter.unparseable',
                    message='frontmatter is not valid YAML: found collections nested too deeply to parse',
                ),
            ),
        ], 'the nesting is one finding on line 1, having no line of its own, and the run checks the other document'

    def test_run_frontmatter_with_an_ungoverned_document_first_still_checks_the_governed_ones_after_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        # corpus `api` sorts before `code`, so its ungoverned document is the first ref the run is handed
        _write(tmp_path, 'docs/__meta__/api.md', b'# Api\n')
        _write(tmp_path, 'docs/__meta__/api.structure.json', NO_FRONTMATTER_STRUCTURE_SPEC.encode())
        _write(tmp_path, 'docs/__meta__/code.md', b'# Code\n')
        _write(tmp_path, 'docs/__meta__/code.structure.json', DESCRIPTION_STRUCTURE_SPEC.encode())
        _write(tmp_path, 'docs/api/intro.md', b'---\nname: "intro"\n---\n')
        _write(tmp_path, 'docs/code/guide.md', b'---\nname: "guide"\ndescription: "A guide"\n---\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_document(database)

        #: Then
        assert [(report.ref.path, report.governed) for report in run.reports] == [
            (RootRelativePath.parse('docs/api/intro.md'), False),
            (RootRelativePath.parse('docs/code/guide.md'), True),
        ], 'the api corpus states no frontmatter schema, and skipping its document does not end the run'
