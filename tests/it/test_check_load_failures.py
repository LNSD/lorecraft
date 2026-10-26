"""`lorecraft check` over a workspace that partly fails to load: each failure reported where it is, the rest checked.

A spec that cannot be used is an error diagnostic at its structure file, under a code of its own, and the
spec parts it would govern are reported as partial coverage while package and schema checks continue. Each test
writes a small workspace of two corpora, `code` and `feat`, with one
namespace spec in `code`, breaks one structure file, and runs the command through Typer's `CliRunner`.

Failures the operating system refuses are not here: a refusal while the snapshot is taken stops the run, so a check
run has none to report. Those refusals are in `test_snapshot_refusals`.
"""

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Final, assert_never

import pytest
from typer.testing import CliRunner

from lorecraft.cli import build_app

runner = CliRunner()

CODE_SPEC: Final[str] = '{"outline": [{"section": "Rule"}, {"any": true}]}'
"""The structure file of corpus `code`: every document opens with a `Rule` section."""

PYTHON_SPEC: Final[str] = '{"outline": [{"section": "Rule"}, {"section": "Checklist"}]}'
"""The structure file of the namespace `python` of corpus `code`: a `Checklist` section follows `Rule`."""

FEAT_SPEC: Final[str] = '{"outline": [{"section": "Usage"}]}'
"""The structure file of corpus `feat`: every document holds a `Usage` section."""

CONTRADICTORY_SPEC: Final[str] = '{"outline": [{"section": "Rule"}], "forbidden": ["Rule"]}'
"""A structure file that requires and forbids one section."""

STATES_NO_RULE: Final[str] = '{}'
"""A structure file that follows the format and states no rule."""

TYPING: Final[str] = '# Typing\n\n## Rule\n\nAnnotate every signature.\n\n## Checklist\n\nCheck it.\n'
"""A document of the `python` namespace that holds to both specs."""

LOGGING_WITHOUT_RULE: Final[str] = '# Logging\n\n## Notes\n\nLog at the edge.\n'
"""A document no namespace governs, which lacks the `Rule` section its corpus asks for."""

LOGGING: Final[str] = '# Logging\n\n## Rule\n\nLog at the edge.\n'
"""A document no namespace governs that holds to its corpus's spec."""

CHECK_WITHOUT_USAGE: Final[str] = '# Check\n\n## Overview\n\nRun it.\n'
"""A document of corpus `feat` that lacks the `Usage` section its corpus asks for."""

STRUCTURE_FILE_OF_CODE: Final[str] = 'docs/__meta__/code.spec.json'
STRUCTURE_FILE_OF_PYTHON: Final[str] = 'docs/__meta__/code-python.spec.json'
STRUCTURE_FILE_OF_FEAT: Final[str] = 'docs/__meta__/feat.spec.json'

# A run that finishes exits 0 when it found nothing and 1 when it found something; 2 is a refused command line.
_RUN_EXIT_CODES: Final[frozenset[int]] = frozenset({0, 1})


def _build_workspace(
    root: Path,
    *,
    code_spec: str | bytes = CODE_SPEC,
    python_spec: str | bytes = PYTHON_SPEC,
    feat_spec: str | bytes = FEAT_SPEC,
    logging: str = LOGGING,
) -> Path:
    """Write the two corpora and their specs under `root`, each file as the case sets it, and return `root`.

    Args:
        root: The directory to write the repository into.
        code_spec: The text, or the bytes, of the structure file of corpus `code`.
        python_spec: The text, or the bytes, of the structure file of its namespace `python`.
        feat_spec: The text, or the bytes, of the structure file of corpus `feat`.
        logging: The text of `docs/code/logging.md`.
    """
    files: dict[str, str | bytes] = {
        STRUCTURE_FILE_OF_CODE: code_spec,
        STRUCTURE_FILE_OF_PYTHON: python_spec,
        STRUCTURE_FILE_OF_FEAT: feat_spec,
        'docs/code/python-typing.md': TYPING,
        'docs/code/logging.md': logging,
        'docs/feat/check.md': CHECK_WITHOUT_USAGE,
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        match content:
            case bytes():
                path.write_bytes(content)
            case str():
                path.write_text(content, encoding='utf-8')
            case _:
                assert_never(content)
    return root


def _check_json(root: Path, *arguments: str) -> tuple[int, dict[str, object]]:
    """Run `lorecraft check` over `root` with JSON output; its exit code and the document it printed.

    Args:
        root: The repository to check.
        arguments: More command-line arguments, such as `--select`.
    """
    result = runner.invoke(build_app(), ['check', '--root', str(root), '--format', 'json', *arguments])
    assert result.exit_code in _RUN_EXIT_CODES, result.output
    document: dict[str, object] = json.loads(result.stdout)
    return result.exit_code, document


def _codes_at(document: dict[str, object], path: str) -> list[str]:
    """The code of each diagnostic a run reported at `path`, in output order.

    Args:
        document: The JSON document of a run.
        path: The root-relative path of the subject.
    """
    diagnostics = document['diagnostics']
    assert isinstance(diagnostics, list), 'the diagnostics of the run are a list'
    return [item['code'] for item in diagnostics if item['path'] == path]


def _severities_at(document: dict[str, object], path: str) -> list[str]:
    """The severity of each diagnostic a run reported at `path`, in output order.

    Args:
        document: The JSON document of a run.
        path: The root-relative path of the subject.
    """
    diagnostics = document['diagnostics']
    assert isinstance(diagnostics, list), 'the diagnostics of the run are a list'
    return [item['severity'] for item in diagnostics if item['path'] == path]


def _engine_diagnostics(document: dict[str, object]) -> list[dict[str, str]]:
    """The diagnostics of a run that the engine raised, those under an `LC` code, in output order.

    Args:
        document: The JSON document of a run.
    """
    diagnostics = document['diagnostics']
    assert isinstance(diagnostics, list), 'the diagnostics of the run are a list'
    return [item for item in diagnostics if item['code'].startswith('LC0')]


@pytest.fixture(scope='function')
def workspace_with_unlistable_meta_directory(tmp_path: Path) -> Iterator[Path]:
    """The workspace with `docs/__meta__` refusing listing, restored afterwards so pytest can clean it up.

    Args:
        tmp_path: Directory the workspace is written into, as its root.
    """
    root = _build_workspace(tmp_path)
    meta = root / 'docs' / '__meta__'
    meta.chmod(0o000)
    yield root
    meta.chmod(0o755)


def _coverage(document: dict[str, object]) -> dict[str, dict[str, object]]:
    """The coverage of a run by subject path.

    Args:
        document: The JSON document of a run.
    """
    coverage = document['coverage']
    assert isinstance(coverage, list), 'the coverage of the run is a list'
    return {item['path']: item for item in coverage}


def _paths(items: list[dict[str, str]]) -> list[str]:
    """The `path` of each diagnostic, in the order given.

    Args:
        items: Diagnostics of a run, as the JSON document lists them.
    """
    return [item['path'] for item in items]


def _codes(items: list[dict[str, str]]) -> list[str]:
    """The `code` of each diagnostic, in the order given.

    Args:
        items: Diagnostics of a run, as the JSON document lists them.
    """
    return [item['code'] for item in items]


def _lines(output: str) -> list[str]:
    """The lines of a run's output, without their line endings.

    Args:
        output: Text a run wrote to one stream.
    """
    return output.splitlines()


def _has_finding(lines: list[str], path: str, severity: str, code: str) -> bool:
    """Whether some line of the short format reports the code, at that severity, at a line of the document.

    Args:
        lines: Lines of a run's short-format output.
        path: Subject path the finding is reported at.
        severity: Severity the finding is printed with, such as `error`.
        code: Rule code the finding carries.
    """
    return any(line.startswith(f'{path}:') and f'{severity}[{code}]' in line for line in lines)


def _skipped_paths(coverage: dict[str, dict[str, object]]) -> list[str]:
    """The path of each document the run skipped, in coverage order.

    Args:
        coverage: Coverage of a run by subject path.
    """
    return [path for path, item in coverage.items() if item['skipped_by']]


def _coverage_of(coverage: dict[str, dict[str, object]], paths: list[str]) -> dict[str, dict[str, object]]:
    """The coverage entries of the given documents alone.

    Args:
        coverage: Coverage of a run by subject path.
        paths: Subject paths whose entries are kept; each must be in the coverage.
    """
    return {path: coverage[path] for path in paths}


@pytest.mark.it
class TestCheckWithAFailedSpec:
    def test_check_with_a_contradictory_structure_file_reports_it_and_checks_the_other_corpus(
        self, tmp_path: Path
    ) -> None:
        #: Given
        root = _build_workspace(tmp_path, code_spec=CONTRADICTORY_SPEC)

        #: When
        exit_code, document = _check_json(root)

        #: Then
        assert _codes_at(document, STRUCTURE_FILE_OF_CODE) == ['LC004'], (
            'an error diagnostic is reported on the invalid structure file, under its code'
        )
        assert _severities_at(document, STRUCTURE_FILE_OF_CODE) == ['error'], 'it is reported as an error'
        assert _codes_at(document, 'docs/feat/check.md') == ['OUT006'], (
            'the document of the other corpus gets the diagnostic it gets with no broken file'
        )
        assert _severities_at(document, 'docs/feat/check.md') == ['error'], 'it is reported as an error'
        assert exit_code == 1, 'the run fails with the status for findings'

    def test_check_with_a_structure_file_that_is_not_utf8_reports_it_and_checks_the_other_corpus(
        self, tmp_path: Path
    ) -> None:
        #: Given
        root = _build_workspace(tmp_path, code_spec=b'{"tokens": 4000, "title": {"pattern": "caf\xe9"}}')

        #: When
        exit_code, document = _check_json(root)

        #: Then
        assert _codes_at(document, STRUCTURE_FILE_OF_CODE) == ['LC001'], (
            'a structure file that does not decode is reported as any file that does not decode'
        )
        assert _severities_at(document, STRUCTURE_FILE_OF_CODE) == ['error'], 'it is reported as an error'
        assert _codes_at(document, 'docs/feat/check.md') == ['OUT006'], (
            'every corpus the file does not govern is checked'
        )
        assert _severities_at(document, 'docs/feat/check.md') == ['error'], 'it is reported as an error'
        assert exit_code == 1, 'the run fails with the status for findings'

    def test_check_with_a_failed_namespace_spec_reports_partial_coverage_for_each_document_it_governs(
        self, tmp_path: Path
    ) -> None:
        #: Given
        root = _build_workspace(tmp_path, python_spec=STATES_NO_RULE, logging=LOGGING_WITHOUT_RULE)

        #: When
        exit_code, document = _check_json(root)

        #: Then
        coverage = _coverage(document)
        assert coverage['docs/code/python-typing.md'] == {
            'path': 'docs/code/python-typing.md',
            'ungoverned': ['frontmatter', 'structure', 'outline', 'budget'],
            'cause': None,
            'skipped_by': [],
        }, 'the affected spec parts are reported, while rules no spec part gates can judge the item'
        assert _codes_at(document, 'docs/code/python-typing.md') == [], 'the failed namespace gates are suppressed'
        assert coverage['docs/code/logging.md']['skipped_by'] == [], 'the other document is judged, not skipped'
        assert _codes_at(document, 'docs/code/logging.md') == ['OUT006'], (
            "the corpus's other documents are checked against the corpus spec"
        )
        assert _severities_at(document, 'docs/code/logging.md') == ['error'], 'a missing section is an error'
        assert _codes_at(document, STRUCTURE_FILE_OF_PYTHON) == ['LC003'], (
            'the failure is reported at its structure file'
        )
        assert _severities_at(document, STRUCTURE_FILE_OF_PYTHON) == ['error'], 'it is reported as an error'
        assert exit_code == 1, 'the run fails with the status for findings'

    def test_check_with_a_failed_corpus_spec_reports_partial_coverage_for_every_document_it_governs(
        self, tmp_path: Path
    ) -> None:
        #: Given
        root = _build_workspace(tmp_path, code_spec=STATES_NO_RULE, logging=LOGGING_WITHOUT_RULE)

        #: When
        _exit_code, document = _check_json(root)

        #: Then
        coverage = _coverage(document)
        assert coverage['docs/code/python-typing.md']['ungoverned'] == [
            'frontmatter',
            'structure',
            'outline',
            'budget',
        ], 'the failed corpus gates suppress spec rules while package-level checks still run'
        assert coverage['docs/code/logging.md']['ungoverned'] == ['frontmatter', 'structure', 'outline', 'budget']
        assert coverage['docs/code/logging.md']['skipped_by'] == []
        assert _codes_at(document, 'docs/code/logging.md') == [], 'the structure-gated findings are suppressed'

    def test_check_with_two_failed_layers_reports_suppressed_parts_once(self, tmp_path: Path) -> None:
        #: Given
        root = _build_workspace(tmp_path, code_spec=STATES_NO_RULE, python_spec=STATES_NO_RULE)

        #: When
        _exit_code, document = _check_json(root)

        #: Then
        assert _coverage(document)['docs/code/python-typing.md']['ungoverned'] == [
            'frontmatter',
            'structure',
            'outline',
            'budget',
        ], 'each suppressed part appears once even when multiple layers failed'

    def test_check_with_a_failed_spec_reports_each_failure_once_whatever_it_governs(self, tmp_path: Path) -> None:
        #: Given
        root = _build_workspace(tmp_path, code_spec=STATES_NO_RULE)

        #: When
        _exit_code, document = _check_json(root)

        #: Then
        engine = _engine_diagnostics(document)
        assert _paths(engine) == [STRUCTURE_FILE_OF_CODE], (
            'one diagnostic at the structure file, though it governs two documents'
        )
        assert _codes(engine) == ['LC003'], 'it is the failure the file has'

    def test_check_with_a_failed_spec_prints_suppressed_parts_in_coverage(self, tmp_path: Path) -> None:
        #: Given
        root = _build_workspace(tmp_path, python_spec=STATES_NO_RULE)
        app = build_app()
        arguments = ['check', '--root', str(root), '--format', 'short']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        lines = _lines(result.stdout)
        assert f'{STRUCTURE_FILE_OF_PYTHON}: error[LC003]: structure file states no rule' in lines, (
            'the failure is one line at its structure file'
        )
        assert _has_finding(lines, 'docs/feat/check.md', 'error', 'OUT006'), 'the other findings are printed with it'
        assert 'docs/code/python-typing.md: ungoverned for frontmatter, structure, outline, budget' in result.stderr, (
            'the checked item lists the parts whose rules the failed layer suppressed'
        )
        assert result.exit_code == 1, 'the run fails with the status for findings'


@pytest.mark.it
class TestCheckWithALoadFailureAndNothingElseWrong:
    def test_check_with_a_failed_spec_and_clean_documents_never_exits_successfully(self, tmp_path: Path) -> None:
        #: Given
        root = _build_workspace(tmp_path, python_spec=STATES_NO_RULE, feat_spec='{"tokens": 4000}')

        #: When
        exit_code, document = _check_json(root)

        #: Then
        assert exit_code == 1, 'a run that reports a load failure exits with the status for findings, never 0'
        assert document['summary'] == {'subjects': 3, 'errors': 1, 'warnings': 0}, (
            'the failure is the one error, and it is no subject'
        )

    def test_check_with_every_spec_loading_and_clean_documents_exits_successfully(self, tmp_path: Path) -> None:
        #: Given
        root = _build_workspace(tmp_path, feat_spec='{"tokens": 4000}')

        #: When
        exit_code, document = _check_json(root)

        #: Then
        assert exit_code == 0, 'nothing failed and nothing was found, so the run succeeds'
        coverage = _coverage(document)
        assert _skipped_paths(coverage) == [], 'no document was skipped'


@pytest.mark.it
class TestCheckLeavesWhatAFailureDoesNotTouchAsItWas:
    def test_check_with_a_failed_namespace_spec_gives_every_other_document_the_diagnostics_it_gets_fixed(
        self, tmp_path: Path
    ) -> None:
        #: Given
        fixed_root = _build_workspace(tmp_path / 'fixed', logging=LOGGING_WITHOUT_RULE)
        broken_root = _build_workspace(tmp_path / 'broken', python_spec=STATES_NO_RULE, logging=LOGGING_WITHOUT_RULE)
        _fixed_code, fixed = _check_json(fixed_root)
        fixed_coverage = _coverage(fixed)
        # The only document the failed namespace spec governs is the Python typing rule
        untouched = [path for path in fixed_coverage if path != 'docs/code/python-typing.md']

        #: When
        _broken_code, broken = _check_json(broken_root)

        #: Then
        assert _codes_at(broken, 'docs/code/logging.md') == _codes_at(fixed, 'docs/code/logging.md'), (
            'a document the failed spec does not govern gets what it gets with the spec fixed'
        )
        assert _codes_at(broken, 'docs/feat/check.md') == _codes_at(fixed, 'docs/feat/check.md'), (
            'so does a document of another corpus'
        )
        assert _coverage_of(_coverage(broken), untouched) == _coverage_of(fixed_coverage, untouched), (
            'the coverage of the documents the failure does not touch is the coverage they have fixed'
        )

    def test_check_with_several_failures_reports_each_and_checks_the_rest(self, tmp_path: Path) -> None:
        #: Given
        root = _build_workspace(
            tmp_path,
            python_spec=STATES_NO_RULE,
            feat_spec=b'{"tokens": 4000, "title": {"pattern": "caf\xe9"}}',
            logging=LOGGING_WITHOUT_RULE,
        )

        #: When
        exit_code, document = _check_json(root)

        #: Then
        assert _codes_at(document, STRUCTURE_FILE_OF_PYTHON) == ['LC003'], 'the empty namespace spec is reported'
        assert _severities_at(document, STRUCTURE_FILE_OF_PYTHON) == ['error'], 'it is reported as an error'
        assert _codes_at(document, STRUCTURE_FILE_OF_FEAT) == ['LC001'], 'the corpus spec that is not UTF-8 is reported'
        assert _severities_at(document, STRUCTURE_FILE_OF_FEAT) == ['error'], 'it is reported as an error'
        assert _codes_at(document, 'docs/code/logging.md') == ['OUT006'], 'what no failure touches is still checked'
        assert _severities_at(document, 'docs/code/logging.md') == ['error'], 'it is reported as an error'
        coverage = _coverage(document)
        assert coverage['docs/code/python-typing.md']['ungoverned'] == ['frontmatter', 'structure', 'outline', 'budget']
        assert coverage['docs/feat/check.md']['ungoverned'] == ['frontmatter', 'structure', 'outline', 'budget']
        assert exit_code == 1, 'no failure inside the declaration stops the run'

    def test_check_with_one_outline_code_selected_still_reports_a_load_failure(self, tmp_path: Path) -> None:
        #: Given
        root = _build_workspace(tmp_path, python_spec=STATES_NO_RULE)

        #: When
        exit_code, document = _check_json(root, '--select', 'OUT006')

        #: Then
        assert _codes_at(document, STRUCTURE_FILE_OF_PYTHON) == ['LC003'], (
            'no selection turns a load failure off, as none turns off a file that cannot be decoded'
        )
        assert _severities_at(document, STRUCTURE_FILE_OF_PYTHON) == ['error'], 'it is reported as an error'
        assert exit_code == 1, 'the run fails with the status for findings'

    def test_check_with_one_frontmatter_code_selected_still_reports_a_load_failure(self, tmp_path: Path) -> None:
        #: Given
        root = _build_workspace(tmp_path, python_spec=STATES_NO_RULE)

        #: When
        exit_code, document = _check_json(root, '--select', 'LC201')

        #: Then
        assert _codes_at(document, STRUCTURE_FILE_OF_PYTHON) == ['LC003'], (
            'no selection turns a load failure off, as none turns off a file that cannot be decoded'
        )
        assert _severities_at(document, STRUCTURE_FILE_OF_PYTHON) == ['error'], 'it is reported as an error'
        assert exit_code == 1, 'the run fails with the status for findings'

    def test_check_with_one_length_rule_selected_still_reports_a_load_failure(self, tmp_path: Path) -> None:
        #: Given
        root = _build_workspace(tmp_path, python_spec=STATES_NO_RULE)

        #: When
        exit_code, document = _check_json(root, '--select', 'LEN001')

        #: Then
        assert _codes_at(document, STRUCTURE_FILE_OF_PYTHON) == ['LC003'], (
            'no selection turns a load failure off, as none turns off a file that cannot be decoded'
        )
        assert _severities_at(document, STRUCTURE_FILE_OF_PYTHON) == ['error'], 'it is reported as an error'
        assert exit_code == 1, 'the run fails with the status for findings'


@pytest.mark.it
@pytest.mark.skipif(os.geteuid() == 0, reason='root ignores directory permissions')
class TestCheckWithAnUnlistableMetaDirectory:
    def test_check_with_a_meta_directory_that_cannot_be_listed_stops_before_checking_anything(
        self, workspace_with_unlistable_meta_directory: Path
    ) -> None:
        #: Given
        root = workspace_with_unlistable_meta_directory
        app = build_app()
        arguments = ['check', '--root', str(root), '--format', 'json']

        #: When
        result = runner.invoke(app, arguments)

        #: Then
        assert result.exit_code == 2, 'with no spec known nothing can be checked, so the run is an error'
        assert result.stdout == '', 'and no report is printed, since one would read as a clean result'
        assert 'error: cannot list directory docs/__meta__: permission denied' in result.stderr, (
            'the directory is printed as a failure, as it is when the root cannot be found'
        )
