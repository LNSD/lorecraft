"""The budget run over a database opened on a snapshot of a real tree.

``run_budget`` reads everything through the database, and the database answers from one snapshot, so the run
reports the tree as the scan saw it: every kind of report, and the budgets layered by filename.
"""

from pathlib import Path
from textwrap import dedent
from typing import Final

import pytest

from lorecraft.checks import CheckRun, Database, run_budget
from lorecraft.core.path import RootRelativePath
from lorecraft.project.layout import SNAPSHOT_SCOPE
from lorecraft.vfs import take_snapshot

# A rule document: at most 40 tokens for the whole file, and a Checklist, so the structure check has a rule too.
CODE_STRUCTURE_SPEC: Final[str] = dedent(
    """
    {
      "tokens": 40,
      "outline": [{"any": true}, {"section": "Checklist"}]
    }
    """
)

# The python layer: a budget of 12 tokens, tighter than the corpus one.
PYTHON_STRUCTURE_SPEC: Final[str] = dedent(
    """
    {
      "tokens": 12
    }
    """
)

# The feat corpus: a structure spec that sets no budget.
FEAT_STRUCTURE_SPEC: Final[str] = dedent(
    """
    {
      "empty_sections": "forbidden"
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
    return run_budget(database, database.model().documents())


@pytest.fixture(scope='function')
def lorecraft_tree(tmp_path: Path) -> Path:
    """A tree shaped like this repository, built to produce every kind of report.

    Corpus ``code`` is governed by a corpus budget and a tighter ``python`` layer: one document within its budget,
    one whose code block puts it over the budget though it holds little prose, one python document within the
    corpus budget but over the python one, and one that is not UTF-8. Corpus ``feat`` has a structure spec that
    sets no budget, so its document is ungoverned.
    """
    costly_example = b'```python\n' + b'value = compute(value)\n' * 8 + b'```\n'
    _write(tmp_path, 'docs/__meta__/code.md', b'# Code\n')
    _write(tmp_path, 'docs/__meta__/code.structure.json', CODE_STRUCTURE_SPEC.encode())
    _write(tmp_path, 'docs/__meta__/code-python.md', b'# Code Python\n')
    _write(tmp_path, 'docs/__meta__/code-python.structure.json', PYTHON_STRUCTURE_SPEC.encode())
    _write(tmp_path, 'docs/__meta__/feat.md', b'# Feat\n')
    _write(tmp_path, 'docs/__meta__/feat.structure.json', FEAT_STRUCTURE_SPEC.encode())
    _write(tmp_path, 'docs/code/clean.md', b'# Clean\n\n## Rule\n\ntext\n\n## Checklist\n\n- [ ] item\n')
    _write(tmp_path, 'docs/code/costly.md', b'# Costly\n\n## Rule\n\ntext\n\n' + costly_example)
    _write(tmp_path, 'docs/code/python-typing.md', b'# Typing\n\n## Rule\n\ntext\n\n## Checklist\n\n- [ ] item\n')
    _write(tmp_path, 'docs/code/latin.md', b'# Caf\xe9\n')
    _write(tmp_path, 'docs/feat/overview.md', b'# Overview\n')
    return tmp_path


@pytest.mark.it
class TestRunBudget:
    def test_run_budget_over_a_snapshot_reports_one_rule_per_document_over_its_budget(
        self, lorecraft_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(lorecraft_tree, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_document(database)

        #: Then
        findings = sorted((str(finding.path), finding.rule, finding.message) for finding in run.findings())
        assert findings == [
            (
                'docs/code/costly.md',
                'budget.tokens',
                '54 tokens; the budget is 40 (per code.structure.json)',
            ),
            ('docs/code/latin.md', 'budget.undecodable', 'document is not valid UTF-8'),
            (
                'docs/code/python-typing.md',
                'budget.tokens',
                '17 tokens; the budget is 12 (per code-python.structure.json)',
            ),
        ], 'each document over a budget yields one finding, quoting the layer whose budget it exceeds'

    def test_run_budget_over_a_snapshot_reports_a_corpus_whose_specs_set_no_budget_as_ungoverned(
        self, lorecraft_tree: Path
    ) -> None:
        #: Given
        database = Database(take_snapshot(lorecraft_tree, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_document(database)

        #: Then
        ungoverned = [report.ref.path for report in run.reports if not report.governed]
        assert ungoverned == [RootRelativePath.parse('docs/feat/overview.md')], (
            'the feat structure spec sets no `tokens`, so its one document is ungoverned for the budget'
        )

    def test_run_budget_with_an_ungoverned_document_first_still_checks_the_governed_ones_after_it(
        self, tmp_path: Path
    ) -> None:
        #: Given
        # corpus `api` sorts before `code`, so its ungoverned document is the first ref the run is handed
        _write(tmp_path, 'docs/__meta__/api.md', b'# Api\n')
        _write(tmp_path, 'docs/__meta__/api.structure.json', FEAT_STRUCTURE_SPEC.encode())
        _write(tmp_path, 'docs/__meta__/code.md', b'# Code\n')
        _write(tmp_path, 'docs/__meta__/code.structure.json', CODE_STRUCTURE_SPEC.encode())
        _write(tmp_path, 'docs/api/intro.md', b'# Intro\n')
        _write(tmp_path, 'docs/code/guide.md', b'# Guide\n\n## Rule\n\ntext\n\n## Checklist\n\n- [ ] item\n')
        database = Database(take_snapshot(tmp_path, SNAPSHOT_SCOPE))

        #: When
        run = _run_every_document(database)

        #: Then
        assert [(report.ref.path, report.governed) for report in run.reports] == [
            (RootRelativePath.parse('docs/api/intro.md'), False),
            (RootRelativePath.parse('docs/code/guide.md'), True),
        ], 'the api corpus sets no budget, and skipping its document does not end the run'
