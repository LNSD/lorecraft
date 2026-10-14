"""`lorecraft check` over a workspace that partly fails to load: each failure reported where it is, the rest checked.

A meta spec that cannot be used is an error diagnostic at its structure file, under a code of its own, and every
document it governs is listed in coverage as skipped, never reported as clean; every document it does not govern is
checked as if nothing had failed. Each test writes a small workspace of two corpora, `code` and `feat`, with one
namespace meta spec in `code`, breaks one structure file, and runs the command through Typer's `CliRunner`.

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
"""A document of the `python` namespace that holds to both meta specs."""

LOGGING_WITHOUT_RULE: Final[str] = '# Logging\n\n## Notes\n\nLog at the edge.\n'
"""A document no namespace governs, which lacks the `Rule` section its corpus asks for."""

LOGGING: Final[str] = '# Logging\n\n## Rule\n\nLog at the edge.\n'
"""A document no namespace governs that holds to its corpus's meta spec."""

CHECK_WITHOUT_USAGE: Final[str] = '# Check\n\n## Overview\n\nRun it.\n'
"""A document of corpus `feat` that lacks the `Usage` section its corpus asks for."""

STRUCTURE_FILE_OF_CODE: Final[str] = 'docs/__meta__/code.structure.json'
STRUCTURE_FILE_OF_PYTHON: Final[str] = 'docs/__meta__/code-python.structure.json'
STRUCTURE_FILE_OF_FEAT: Final[str] = 'docs/__meta__/feat.structure.json'


def _write_workspace(
    root: Path,
    *,
    code_spec: str | bytes = CODE_SPEC,
    python_spec: str | bytes = PYTHON_SPEC,
    feat_spec: str | bytes = FEAT_SPEC,
    logging: str = LOGGING,
) -> Path:
    """Write the two corpora and their meta specs under `root`, each file as the case sets it, and return `root`.

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
    assert result.exit_code in (0, 1), result.output
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
    return [item for item in diagnostics if item['code'].startswith('LC')]


@pytest.fixture(scope='function')
def workspace_with_unlistable_meta_directory(tmp_path: Path) -> Iterator[Path]:
    """The workspace with `docs/__meta__` refusing listing, restored afterwards so pytest can clean it up.

    Args:
        tmp_path: Directory the workspace is written into, as its root.
    """
    root = _write_workspace(tmp_path)
    meta = root / 'docs' / '__meta__'
    meta.chmod(0o000)
    yield root
    meta.chmod(0o755)


@pytest.fixture(scope='function')
def workspace_with_unreadable_shadowed_code_structure_file(tmp_path: Path) -> Iterator[Path]:
    """The workspace whose `code.structure.json` is unreadable and shadowed by `code.spec.json`, restored afterwards.

    Args:
        tmp_path: Directory the workspace is written into, as its root.
    """
    root = _write_workspace(tmp_path)
    (root / 'docs/__meta__/code.spec.json').write_text(CODE_SPEC, encoding='utf-8')
    legacy = root / STRUCTURE_FILE_OF_CODE
    legacy.chmod(0o000)
    yield root
    legacy.chmod(0o644)


@pytest.fixture(scope='function')
def workspace_with_unreadable_shadowed_python_structure_file(tmp_path: Path) -> Iterator[Path]:
    """The workspace whose `code-python.structure.json` is unreadable and shadowed by `code-python.spec.json`.

    The file is restored afterwards.

    Args:
        tmp_path: Directory the workspace is written into, as its root.
    """
    root = _write_workspace(tmp_path)
    (root / 'docs/__meta__/code-python.spec.json').write_text(PYTHON_SPEC, encoding='utf-8')
    legacy = root / STRUCTURE_FILE_OF_PYTHON
    legacy.chmod(0o000)
    yield root
    legacy.chmod(0o644)


def _coverage(document: dict[str, object]) -> dict[str, dict[str, object]]:
    """The coverage of a run by subject path.

    Args:
        document: The JSON document of a run.
    """
    coverage = document['coverage']
    assert isinstance(coverage, list), 'the coverage of the run is a list'
    return {item['path']: item for item in coverage}


@pytest.mark.it
class TestCheckWithAFailedMetaSpec:
    def test_check_with_a_contradictory_structure_file_reports_it_and_checks_the_other_corpus(
        self, tmp_path: Path
    ) -> None:
        #: Given
        root = _write_workspace(tmp_path, code_spec=CONTRADICTORY_SPEC)

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
        root = _write_workspace(tmp_path, code_spec=b'{"tokens": 4000, "title": {"pattern": "caf\xe9"}}')

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

    def test_check_with_a_failed_namespace_spec_lists_each_document_it_governs_as_skipped(self, tmp_path: Path) -> None:
        #: Given
        root = _write_workspace(tmp_path, python_spec=STATES_NO_RULE, logging=LOGGING_WITHOUT_RULE)

        #: When
        exit_code, document = _check_json(root)

        #: Then
        coverage = _coverage(document)
        assert coverage['docs/code/python-typing.md'] == {
            'path': 'docs/code/python-typing.md',
            'ungoverned': [],
            'skipped_by': [STRUCTURE_FILE_OF_PYTHON],
        }, 'the document the namespace governs is skipped, naming the failed meta spec'
        assert _codes_at(document, 'docs/code/python-typing.md') == [], 'no rule judged the skipped document'
        assert coverage['docs/code/logging.md']['skipped_by'] == [], 'the other document is judged, not skipped'
        assert _codes_at(document, 'docs/code/logging.md') == ['OUT006'], (
            "the corpus's other documents are checked against the corpus meta spec"
        )
        assert _severities_at(document, 'docs/code/logging.md') == ['error'], 'a missing section is an error'
        assert _codes_at(document, STRUCTURE_FILE_OF_PYTHON) == ['LC003'], (
            'the failure is reported at its structure file'
        )
        assert _severities_at(document, STRUCTURE_FILE_OF_PYTHON) == ['error'], 'it is reported as an error'
        assert exit_code == 1, 'the run fails with the status for findings'

    def test_check_with_a_failed_corpus_spec_skips_every_document_of_the_corpus_though_its_namespaces_load(
        self, tmp_path: Path
    ) -> None:
        #: Given
        root = _write_workspace(tmp_path, code_spec=STATES_NO_RULE, logging=LOGGING_WITHOUT_RULE)

        #: When
        _exit_code, document = _check_json(root)

        #: Then
        coverage = _coverage(document)
        assert coverage['docs/code/python-typing.md']['skipped_by'] == [STRUCTURE_FILE_OF_CODE], (
            'the corpus meta spec governs each document, so a document its namespace also governs is skipped for it'
        )
        assert coverage['docs/code/logging.md']['skipped_by'] == [STRUCTURE_FILE_OF_CODE], 'the whole corpus is skipped'
        assert _codes_at(document, 'docs/code/logging.md') == [], 'no rule judged a skipped document'

    def test_check_with_two_failed_layers_names_both_for_the_document_they_govern(self, tmp_path: Path) -> None:
        #: Given
        root = _write_workspace(tmp_path, code_spec=STATES_NO_RULE, python_spec=STATES_NO_RULE)

        #: When
        _exit_code, document = _check_json(root)

        #: Then
        assert _coverage(document)['docs/code/python-typing.md']['skipped_by'] == [
            STRUCTURE_FILE_OF_CODE,
            STRUCTURE_FILE_OF_PYTHON,
        ], 'each failed layer is named, corpus spec first'

    def test_check_with_a_failed_meta_spec_reports_each_failure_once_whatever_it_governs(self, tmp_path: Path) -> None:
        #: Given
        root = _write_workspace(tmp_path, code_spec=STATES_NO_RULE)

        #: When
        _exit_code, document = _check_json(root)

        #: Then
        engine = _engine_diagnostics(document)
        assert [item['path'] for item in engine] == [STRUCTURE_FILE_OF_CODE], (
            'one diagnostic at the structure file, though it governs two documents'
        )
        assert [item['code'] for item in engine] == ['LC003'], 'it is the failure the file has'

    def test_check_with_a_failed_meta_spec_prints_each_skipped_document_in_the_coverage(self, tmp_path: Path) -> None:
        #: Given
        root = _write_workspace(tmp_path, python_spec=STATES_NO_RULE)

        #: When
        result = runner.invoke(build_app(), ['check', '--root', str(root), '--format', 'short'])

        #: Then
        lines = result.stdout.splitlines()
        assert f'{STRUCTURE_FILE_OF_PYTHON}: error[LC003]: structure file states no rule' in lines, (
            'the failure is one line at its structure file'
        )
        assert any(line.startswith('docs/feat/check.md:') and 'error[OUT006]' in line for line in lines), (
            'the other findings are printed with it'
        )
        assert (
            'docs/code/python-typing.md: skipped, governed by a structure file that failed to load: '
            f'{STRUCTURE_FILE_OF_PYTHON}'
        ) in result.stderr, 'the skipped document is listed in coverage with the file that caused it'
        assert result.exit_code == 1, 'the run fails with the status for findings'


@pytest.mark.it
class TestCheckWithALoadFailureAndNothingElseWrong:
    def test_check_with_a_failed_meta_spec_and_clean_documents_never_exits_successfully(self, tmp_path: Path) -> None:
        #: Given
        root = _write_workspace(tmp_path, python_spec=STATES_NO_RULE, feat_spec='{"tokens": 4000}')

        #: When
        exit_code, document = _check_json(root)

        #: Then
        assert exit_code == 1, 'a run that reports a load failure exits with the status for findings, never 0'
        assert document['summary'] == {'subjects': 3, 'errors': 1, 'warnings': 0}, (
            'the failure is the one error, and it is no subject'
        )

    def test_check_with_every_meta_spec_loading_and_clean_documents_exits_successfully(self, tmp_path: Path) -> None:
        #: Given
        root = _write_workspace(tmp_path, feat_spec='{"tokens": 4000}')

        #: When
        exit_code, document = _check_json(root)

        #: Then
        assert exit_code == 0, 'nothing failed and nothing was found, so the run succeeds'
        coverage = _coverage(document)
        assert [path for path, item in coverage.items() if item['skipped_by']] == [], 'no document was skipped'


@pytest.mark.it
class TestCheckLeavesWhatAFailureDoesNotTouchAsItWas:
    def test_check_with_a_failed_namespace_spec_gives_every_other_document_the_diagnostics_it_gets_fixed(
        self, tmp_path: Path
    ) -> None:
        #: Given
        fixed_root = _write_workspace(tmp_path / 'fixed', logging=LOGGING_WITHOUT_RULE)
        broken_root = _write_workspace(tmp_path / 'broken', python_spec=STATES_NO_RULE, logging=LOGGING_WITHOUT_RULE)
        _fixed_code, fixed = _check_json(fixed_root)
        fixed_coverage = _coverage(fixed)
        # The only document the failed namespace spec governs is the Python typing rule
        untouched = [path for path in fixed_coverage if path != 'docs/code/python-typing.md']

        #: When
        _broken_code, broken = _check_json(broken_root)

        #: Then
        assert _codes_at(broken, 'docs/code/logging.md') == _codes_at(fixed, 'docs/code/logging.md'), (
            'a document the failed meta spec does not govern gets what it gets with the meta spec fixed'
        )
        assert _codes_at(broken, 'docs/feat/check.md') == _codes_at(fixed, 'docs/feat/check.md'), (
            'so does a document of another corpus'
        )
        assert {path: _coverage(broken)[path] for path in untouched} == {
            path: fixed_coverage[path] for path in untouched
        }, 'the coverage of the documents the failure does not touch is the coverage they have fixed'

    def test_check_with_several_failures_reports_each_and_checks_the_rest(self, tmp_path: Path) -> None:
        #: Given
        root = _write_workspace(
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
        assert coverage['docs/code/python-typing.md']['skipped_by'] == [STRUCTURE_FILE_OF_PYTHON], (
            'the namespace spec failed, so the document it governs is skipped'
        )
        assert coverage['docs/feat/check.md']['skipped_by'] == [STRUCTURE_FILE_OF_FEAT], (
            'the corpus spec failed, so the document it governs is skipped'
        )
        assert exit_code == 1, 'no failure inside the declaration stops the run'

    def test_check_with_the_outline_group_selected_still_reports_a_load_failure(self, tmp_path: Path) -> None:
        #: Given
        root = _write_workspace(tmp_path, python_spec=STATES_NO_RULE)

        #: When
        exit_code, document = _check_json(root, '--select', 'OUT')

        #: Then
        assert _codes_at(document, STRUCTURE_FILE_OF_PYTHON) == ['LC003'], (
            'no selection turns a load failure off, as none turns off a file that cannot be decoded'
        )
        assert _severities_at(document, STRUCTURE_FILE_OF_PYTHON) == ['error'], 'it is reported as an error'
        assert exit_code == 1, 'the run fails with the status for findings'

    def test_check_with_the_frontmatter_group_selected_still_reports_a_load_failure(self, tmp_path: Path) -> None:
        #: Given
        root = _write_workspace(tmp_path, python_spec=STATES_NO_RULE)

        #: When
        exit_code, document = _check_json(root, '--select', 'FM')

        #: Then
        assert _codes_at(document, STRUCTURE_FILE_OF_PYTHON) == ['LC003'], (
            'no selection turns a load failure off, as none turns off a file that cannot be decoded'
        )
        assert _severities_at(document, STRUCTURE_FILE_OF_PYTHON) == ['error'], 'it is reported as an error'
        assert exit_code == 1, 'the run fails with the status for findings'

    def test_check_with_one_length_rule_selected_still_reports_a_load_failure(self, tmp_path: Path) -> None:
        #: Given
        root = _write_workspace(tmp_path, python_spec=STATES_NO_RULE)

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

        #: When
        result = runner.invoke(build_app(), ['check', '--root', str(root), '--format', 'json'])

        #: Then
        assert result.exit_code == 2, 'with no meta spec known nothing can be checked, so the run is an error'
        assert result.stdout == '', 'and no report is printed, since one would read as a clean result'
        assert 'error: cannot list directory docs/__meta__: permission denied' in result.stderr, (
            'the directory is printed as a failure, as it is when the root cannot be found'
        )


@pytest.mark.it
@pytest.mark.skipif(os.geteuid() == 0, reason='root ignores file permissions')
class TestCheckWithAShadowedLegacyStructureFile:
    def test_check_with_an_unreadable_legacy_file_beside_a_spec_json_ignores_it_and_checks(
        self, workspace_with_unreadable_shadowed_code_structure_file: Path
    ) -> None:
        #: Given
        # `code.spec.json` takes over from `code.structure.json`, which is then ignored, even unreadable.
        root = workspace_with_unreadable_shadowed_code_structure_file

        #: When
        exit_code, document = _check_json(root)

        #: Then
        assert exit_code == 1, 'the run is a normal check run, with the finding of the feat document'
        assert _codes_at(document, STRUCTURE_FILE_OF_CODE) == [], 'the shadowed legacy file reports nothing'
        assert _codes_at(document, 'docs/feat/check.md') == ['OUT006'], 'and the documents are checked as usual'

    def test_check_with_an_unreadable_legacy_namespace_file_beside_a_spec_json_ignores_it(
        self, workspace_with_unreadable_shadowed_python_structure_file: Path
    ) -> None:
        #: Given
        # The namespace spec `code-python` has `.spec.json` too; its legacy file is unreadable and ignored.
        root = workspace_with_unreadable_shadowed_python_structure_file

        #: When
        exit_code, document = _check_json(root)

        #: Then
        assert exit_code == 1, 'the run is a normal check run, with the finding of the feat document'
        assert _codes_at(document, STRUCTURE_FILE_OF_PYTHON) == [], 'the shadowed legacy file reports nothing'
        assert _codes_at(document, 'docs/feat/check.md') == ['OUT006'], 'and the documents are checked as usual'
