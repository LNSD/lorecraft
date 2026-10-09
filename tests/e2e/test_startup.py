"""What the command line imports before it does anything.

`--version`, `--help` and `version` import neither the rules engine nor the rules, so they do not pay for them.

Each test runs the entry point in a fresh interpreter, because `sys.modules` of the test process already holds
everything the other tests imported, and reads back which modules of the package that run loaded. `check` is the
control: it must load them, or the probe would pass for a reason other than the commands being light.
"""

from typing import Final

import pytest

from lib.cli import list_modules_loaded_by_cli

_RULES_ENGINE: Final[str] = 'lorecraft.checks'
_RULES: Final[str] = 'lorecraft.rules'


def _engine_and_rules_loaded_by(*arguments: str) -> list[str]:
    """The modules of the rules engine and of the rules that `lorecraft <arguments>` loaded.

    Args:
        arguments: Command-line arguments passed to `lorecraft`, after the program name.
    """
    prefixes = (_RULES_ENGINE, _RULES)
    return [
        module
        for module in list_modules_loaded_by_cli(*arguments)
        if any(module == prefix or module.startswith(f'{prefix}.') for prefix in prefixes)
    ]


@pytest.mark.e2e
class TestStartupImports:
    def test_version_option_imports_neither_the_rules_engine_nor_the_rules(self) -> None:
        #: When
        loaded = _engine_and_rules_loaded_by('--version')

        #: Then
        assert loaded == [], '`--version` has no use for the rules engine or the rules'

    def test_help_option_imports_neither_the_rules_engine_nor_the_rules(self) -> None:
        #: When
        loaded = _engine_and_rules_loaded_by('--help')

        #: Then
        assert loaded == [], '`--help` lists the commands without running one'

    def test_version_command_imports_neither_the_rules_engine_nor_the_rules(self) -> None:
        #: When
        loaded = _engine_and_rules_loaded_by('version')

        #: Then
        assert loaded == [], '`version` has no use for the rules engine or the rules'

    def test_check_help_imports_neither_the_rules_engine_nor_the_rules(self) -> None:
        #: When
        loaded = _engine_and_rules_loaded_by('check', '--help')

        #: Then
        assert loaded == [], '`check --help` prints the options without running the check'

    def test_check_run_imports_the_rules_engine_and_the_rules(self) -> None:
        #: When
        loaded = _engine_and_rules_loaded_by('check', '--root', '/nonexistent')

        #: Then
        assert _RULES_ENGINE in loaded, 'a `check` run is the control: it needs the rules engine'
        assert _RULES in loaded, 'a `check` run is the control: it needs the rules'
