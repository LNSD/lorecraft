"""The structure run over a database opened on a snapshot of a real tree.

``run_structure`` reads everything through the database, and the database answers from one snapshot, so the
run reports the tree as the scan saw it: every kind of report, and the specifications layered by filename.
"""

from pathlib import Path
from textwrap import dedent
from typing import Final

import pytest

from lorecraft.checks import CheckRun, Database, run_structure
from lorecraft_project.layout import SNAPSHOT_SCOPE
from lorecraft_vfs import RootRelativePath, take_snapshot

# A rule document: one title first, no empty section, the Checklist after the document's own sections.
CODE_STRUCTURE_SPEC: Final[str] = dedent(
    """
    {
      "title": {"count": 1, "first": true},
      "empty_sections": "forbidden",
      "outline": [
        {"any": true},
        {"section": "Checklist"},
        {"section": "References", "optional": true}
      ]
    }
    """
)

# The python layer: References is required, wherever the corpus layer places it.
PYTHON_STRUCTURE_SPEC: Final[str] = dedent(
    """
    {
      "outline": [{"any": true}, {"section": "References"}, {"any": true}]
    }
    """
)


def _write(root: Path, relative: str, data: bytes = b'') -> Path:
    """Write one file under the root, creating its parents, and return its path."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _run_every_document(database: Database) -> CheckRun:
    """Check every document the database's model lists."""
    return run_structure(database, database.model().documents())


@pytest.fixture(scope='function')
def lorecraft_tree(tmp_path: Path) -> Path:
    """A tree shaped like this repository, built to produce every kind of report.

    Corpus ``code`` is governed by a corpus structure and a ``python`` layer: one clean document, one without
    a Checklist, one python document without References, and one that is not UTF-8. Corpus ``feat`` has a
    spec but no structure file, so its document is ungoverned.
    """
    _write(tmp_path, 'docs/__meta__/code.md', b'# Code\n')
    _write(tmp_path, 'docs/__meta__/code.structure.json', CODE_STRUCTURE_SPEC.encode())
    _write(tmp_path, 'docs/__meta__/code-python.md', b'# Code Python\n')
    _write(tmp_path, 'docs/__meta__/code-python.structure.json', PYTHON_STRUCTURE_SPEC.encode())
    _write(tmp_path, 'docs/__meta__/feat.md', b'# Feat\n')
    _write(tmp_path, 'docs/code/clean.md', b'# Clean\n\n## Rule\n\ntext\n\n## Checklist\n\n- [ ] item\n')
    _write(tmp_path, 'docs/code/unchecked.md', b'# Unchecked\n\n## Rule\n\ntext\n')
    _write(tmp_path, 'docs/code/python-typing.md', b'# Typing\n\n## Rule\n\ntext\n\n## Checklist\n\n- [ ] item\n')
    _write(tmp_path, 'docs/code/latin.md', b'# Caf\xe9\n')
    _write(tmp_path, 'docs/feat/overview.md', b'## Empty\n')
    return tmp_path


@pytest.mark.it
class TestRunStructure:
    def test_run_structure_over_a_snapshot_reports_one_rule_per_broken_document(self, lorecraft_tree: Path) -> None:
        #: Given
        database = Database(take_snapshot(lorecraft_tree, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_document(database)

        #: Then
        findings = sorted((str(finding.path), finding.rule, finding.message) for finding in run.findings())
        assert findings == [
            ('docs/code/latin.md', 'structure.undecodable', 'document is not valid UTF-8'),
            (
                'docs/code/python-typing.md',
                'structure.outline',
                'missing required section `References` (per code-python.md)',
            ),
            ('docs/code/unchecked.md', 'structure.outline', 'missing required section `Checklist` (per code.md)'),
        ], 'each broken document yields exactly the finding its defect names, quoting the layer that states it'

    def test_run_structure_over_a_snapshot_reports_a_corpus_without_a_structure_spec_as_ungoverned(
        self, lorecraft_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(lorecraft_tree, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_document(database)

        #: Then
        ungoverned = [report.ref.path for report in run.reports if not report.governed]
        assert ungoverned == [RootRelativePath.parse('docs/feat/overview.md')], (
            'the feat corpus has a spec but no structure file, so its one document is ungoverned'
        )
