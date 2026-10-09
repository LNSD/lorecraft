"""The rule cases: every rule code proves it fires, and proves it stays quiet, on a repository on disk.

A case is a directory under `tests/it/rule_cases/<CODE>/<kind>/<case>/` holding `root/`, the repository
`lorecraft check` runs over, and `expected.json`, the diagnostics the run reports, as a list of objects with a
`path`, a `line` (null for a whole file), a `severity` and a `code`; and, only when the repository holds symlinks, a
`links.json` mapping each link's path in the root to the target it holds. The kind is `trigger` for a repository the
code fires on and `near_miss` for one that looks like it could and does not.

The parametrized tests run the checker over every case and compare the diagnostics it prints with the expected ones,
whole: a second code reported on a line, or a diagnostic the case does not list, fails the case, so a pair of codes
that fire together is allowed only where the case that holds the pair declares it. Two more check that a trigger
expects its own code and a near miss does not. The tests that read the registry and the directory tree run nothing:
one names every code that lacks either kind, one every directory named for a code no rule has, and one every entry
that is not a `trigger/` or `near_miss/` directory under a code.
"""

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, TypedDict

import pytest
from typer.testing import CliRunner

from lorecraft import rules
from lorecraft.cli import build_app
from lorecraft.rules.declaration import RemovedRule
from lorecraft.rules.registry import Registry

RULE_CASES_DIRECTORY: Final[Path] = Path(__file__).parent / 'rule_cases'
"""Where the cases live, one directory per rule code."""

TRIGGER: Final[str] = 'trigger'
"""The kind of case whose repository the code fires on."""

NEAR_MISS: Final[str] = 'near_miss'
"""The kind of case whose repository looks like the code could fire on it, and it does not."""

KINDS: Final[tuple[str, ...]] = (TRIGGER, NEAR_MISS)

runner = CliRunner()


class ExpectedDiagnostic(TypedDict):
    """One diagnostic a case expects, as `expected.json` and the JSON report both spell it.

    Attributes:
        path: The file the diagnostic is reported at, relative to the case's `root/`.
        line: The line it points at, or None for a whole file.
        severity: Whether the diagnostic is an error or a warning.
        code: The code of the rule that reported it.
    """

    path: str
    line: int | None
    severity: Literal['error', 'warning']
    code: str


@dataclass(frozen=True)
class RuleCase:
    """One case on disk.

    Attributes:
        code: The rule code the case belongs to, such as `FM001`.
        kind: `trigger` or `near_miss`.
        name: The case's directory name.
        directory: The case's directory, holding `root/` and `expected.json`.
    """

    code: str
    kind: str
    name: str
    directory: Path

    @property
    def id(self) -> str:
        """The case as a test is named after it: `FM001/trigger/document-without-frontmatter`."""
        return f'{self.code}/{self.kind}/{self.name}'

    def expected(self) -> list[ExpectedDiagnostic]:
        """The diagnostics the case declares, in the order the checker prints them."""
        text = (self.directory / 'expected.json').read_text(encoding='utf-8')
        return json.loads(text)

    def write_repository(self, destination: Path) -> Path:
        """Write the case's repository under `destination` and return its root.

        The files of `root/` are copied, and then every symlink `links.json` declares is created, each a path
        relative to the root and the target it holds. A symlink is declared rather than checked in because a copy of
        the tests, such as the one mutation testing runs, turns a checked-in link into the file it leads to, and a
        link that leaves the repository or dangles cannot be copied at all.

        Args:
            destination: A directory the repository is written into, as `destination/root`; usually `tmp_path`.
        """
        root = destination / 'root'
        shutil.copytree(self.directory / 'root', root)
        links_file = self.directory / 'links.json'
        if links_file.exists():
            links: dict[str, str] = json.loads(links_file.read_text(encoding='utf-8'))
            for link, target in links.items():
                path = root / link
                path.parent.mkdir(parents=True, exist_ok=True)
                path.symlink_to(target)
        return root


def discover_cases() -> tuple[RuleCase, ...]:
    """Every case under the rule cases directory, in code, kind and name order."""
    cases: list[RuleCase] = []
    for code_directory in directories_under(RULE_CASES_DIRECTORY):
        for kind in KINDS:
            for case_directory in directories_under(code_directory / kind):
                cases.append(
                    RuleCase(code=code_directory.name, kind=kind, name=case_directory.name, directory=case_directory)
                )
    return tuple(cases)


def directories_under(directory: Path) -> list[Path]:
    """The subdirectories of `directory` in name order; none when it does not exist."""
    if not directory.is_dir():
        return []
    return sorted(entry for entry in directory.iterdir() if entry.is_dir())


def unexpected_entries() -> list[str]:
    """Every entry of the rule cases tree that is not a code directory holding only `trigger/` and `near_miss/`."""
    unexpected: list[str] = []
    for entry in sorted(RULE_CASES_DIRECTORY.iterdir()):
        if not entry.is_dir():
            unexpected.append(entry.name)
            continue
        for child in sorted(entry.iterdir()):
            if not child.is_dir() or child.name not in KINDS:
                unexpected.append(f'{entry.name}/{child.name}')
    return unexpected


def directory_codes() -> set[str]:
    """The code of every directory directly under the rule cases directory, whatever it holds."""
    return {directory.name for directory in directories_under(RULE_CASES_DIRECTORY)}


def reported_codes() -> list[str]:
    """The code of every rule in service and every engine condition: each one a case must cover."""
    registry = Registry.load(rules)
    codes: list[str] = []
    for declaration in registry.rules:
        if not issubclass(declaration, RemovedRule):
            codes.append(str(declaration.CODE))
    return codes


CASES: Final[tuple[RuleCase, ...]] = discover_cases()
TRIGGER_CASES: Final[tuple[RuleCase, ...]] = tuple(case for case in CASES if case.kind == TRIGGER)
NEAR_MISS_CASES: Final[tuple[RuleCase, ...]] = tuple(case for case in CASES if case.kind == NEAR_MISS)


def case_ids(cases: tuple[RuleCase, ...]) -> list[str]:
    """The test ids of `cases`, one per case."""
    return [case.id for case in cases]


@pytest.mark.it
class TestRuleCases:
    @pytest.mark.parametrize('case', CASES, ids=case_ids(CASES))
    def test_check_over_a_rule_case_reports_exactly_its_expected_diagnostics(
        self, case: RuleCase, tmp_path: Path
    ) -> None:
        #: Given
        root = case.write_repository(tmp_path)
        expected = case.expected()

        #: When
        result = runner.invoke(build_app(), ['check', '--root', str(root), '--format', 'json'])

        #: Then
        assert result.exit_code in (0, 1), result.output
        reported = json.loads(result.stdout)['diagnostics']
        actual: list[ExpectedDiagnostic] = []
        for diagnostic in reported:
            actual.append(
                {
                    'path': diagnostic['path'],
                    'line': diagnostic['line'],
                    'severity': diagnostic['severity'],
                    'code': diagnostic['code'],
                }
            )
        assert actual == expected, 'the case reports the diagnostics it declares and no others'

    @pytest.mark.parametrize('case', TRIGGER_CASES, ids=case_ids(TRIGGER_CASES))
    def test_rule_case_with_a_trigger_expects_its_own_code(self, case: RuleCase) -> None:
        #: Given
        expected = case.expected()

        #: When
        declared_codes = [diagnostic['code'] for diagnostic in expected]

        #: Then
        assert case.code in declared_codes, f'a trigger case expects its own code {case.code}'

    @pytest.mark.parametrize('case', NEAR_MISS_CASES, ids=case_ids(NEAR_MISS_CASES))
    def test_rule_case_with_a_near_miss_does_not_expect_its_own_code(self, case: RuleCase) -> None:
        #: Given
        expected = case.expected()

        #: When
        declared_codes = [diagnostic['code'] for diagnostic in expected]

        #: Then
        assert case.code not in declared_codes, f'a near miss does not expect its own code {case.code}'

    def test_rule_cases_directory_with_every_code_in_the_registry_names_no_unknown_code(self) -> None:
        #: Given
        known_codes = set(reported_codes())

        #: When
        codes = directory_codes()

        #: Then
        assert codes <= known_codes, f'directories name codes no rule has: {sorted(codes - known_codes)}'

    def test_rule_cases_directory_with_only_code_directories_holds_no_stray_entry(self) -> None:
        #: Given
        expected: list[str] = []

        #: When
        unexpected = unexpected_entries()

        #: Then
        assert unexpected == expected, f'only <CODE>/trigger and <CODE>/near_miss may exist; found: {unexpected}'

    def test_rule_cases_with_the_registry_cover_every_code_with_a_trigger_and_a_near_miss(self) -> None:
        #: Given
        codes = reported_codes()
        covered = {(case.code, case.kind) for case in CASES}

        #: When
        missing = [f'{code}/{kind}' for code in codes for kind in KINDS if (code, kind) not in covered]

        #: Then
        assert missing == [], f'every code needs a trigger and a near_miss case; missing: {missing}'
