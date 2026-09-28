"""The header run over a database opened on a snapshot of a real tree.

``run_header`` reads everything through the database, and the database answers from one snapshot, so the run
reports the tree as the scan saw it: every kind of report, and nothing written to the disk afterwards.
"""

from pathlib import Path
from typing import Final

import pytest

from lorecraft.checks import Database, HeaderRun, run_header
from lorecraft_project.layout import SNAPSHOT_SCOPE
from lorecraft_vfs import RootRelativePath, take_snapshot

# Requires a string ``description``, so a document without one yields a schema finding.
DESCRIPTION_HEADER_SCHEMA: Final[str] = (
    '{"type": "object", "required": ["description"], "properties": {"description": {"type": "string"}}}'
)


def _write(root: Path, relative: str, data: bytes = b'') -> Path:
    """Write one file under the root, creating its parents, and return its path."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _run_every_document(database: Database) -> HeaderRun:
    """Check every document the database's model lists."""
    return run_header(database, database.model().documents())


@pytest.fixture(scope='function')
def lorecraft_tree(tmp_path: Path) -> Path:
    """A tree shaped like this repository, built to produce every kind of report.

    Corpus ``code`` is governed: one clean document, one misnamed, one without a description, one without
    frontmatter and one that is not UTF-8, plus a nested document the loader never lists. Corpus ``feat``
    has a spec but no header schema, so its document is ungoverned. Beside them sits a loose file under
    ``docs/``.
    """
    _write(tmp_path, 'docs/__meta__/code.md', b'# Code\n')
    _write(tmp_path, 'docs/__meta__/code.header.json', DESCRIPTION_HEADER_SCHEMA.encode())
    _write(tmp_path, 'docs/__meta__/feat.md', b'# Feat\n')
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
class TestRunHeader:
    def test_run_header_over_a_snapshot_reports_one_rule_per_broken_document(self, lorecraft_tree: Path) -> None:
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

    def test_run_header_over_a_snapshot_reports_a_corpus_without_a_header_schema_as_ungoverned(
        self, lorecraft_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(lorecraft_tree, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_document(database)

        #: Then
        ungoverned = [report.ref.path for report in run.reports if not report.aspects]
        assert ungoverned == [RootRelativePath.parse('docs/feat/overview.md')], (
            'the feat corpus has a spec but no header schema, so its one document is ungoverned'
        )

    def test_run_header_after_the_disk_changes_reports_the_tree_the_snapshot_saw(self, lorecraft_tree: Path) -> None:
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
