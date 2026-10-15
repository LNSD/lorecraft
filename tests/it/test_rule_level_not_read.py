"""Levels are applied after detection: no rule reads its level, so what a rule finds never depends on it."""

import ast
from pathlib import Path
from typing import Final

import pytest

REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
RULES_PACKAGE: Final[Path] = REPOSITORY_ROOT / 'src' / 'lorecraft' / 'rules'

# The modules that hold levels or apply them: the declaration of `LEVEL`, and the table that maps it to a severity.
_LEVEL_AWARE_MODULES: Final[frozenset[str]] = frozenset({'declaration.py', 'table.py', 'registry.py'})


@pytest.mark.it
class TestRulesDoNotReadTheirLevel:
    def test_rule_modules_never_access_the_level_attribute(self) -> None:
        #: Given
        rule_modules = [
            path
            for path in RULES_PACKAGE.rglob('*.py')
            if 'tests' not in path.relative_to(RULES_PACKAGE).parts and path.name not in _LEVEL_AWARE_MODULES
        ]

        #: When
        readers = [
            str(path.relative_to(RULES_PACKAGE))
            for path in rule_modules
            if any(
                isinstance(node, ast.Attribute) and node.attr == 'LEVEL'
                for node in ast.walk(ast.parse(path.read_text(encoding='utf-8')))
            )
        ]

        #: Then
        assert rule_modules, 'the scan found the rule modules'
        assert readers == [], 'no rule reads LEVEL; only the table maps a level to a severity'
