"""The check registry a bare ``lorecraft check`` reads: what a check module's registration may and may not do.

The registry is process-wide, so these cases register only the frontmatter check itself, or a rival under its name
that is refused before it is stored; a new name would join every later bare run in the same process.
"""

import pytest

from lorecraft.checks import run_frontmatter

from ..check_run import DocumentCheck, DuplicateCheckError, register_check, registered_checks
from ..commands.check.frontmatter import FRONTMATTER_CHECK


@pytest.mark.unit
class TestRegisterCheck:
    def test_register_check_with_the_same_check_again_keeps_one_entry(self) -> None:
        #: Given
        before = registered_checks()

        #: When
        returned = register_check(FRONTMATTER_CHECK)

        #: Then
        assert returned is FRONTMATTER_CHECK, 'registration returns the check unchanged, so it can be bound to a name'
        assert registered_checks() == before, 'registering the same check twice is a no-op'

    def test_register_check_with_a_different_check_under_a_taken_name_raises_duplicate_check_error(self) -> None:
        #: Given
        rival = DocumentCheck(name=FRONTMATTER_CHECK.name, run=run_frontmatter, ungoverned='another message')

        #: When
        with pytest.raises(DuplicateCheckError) as exc_info:
            register_check(rival)

        #: Then
        assert FRONTMATTER_CHECK.name in str(exc_info.value), 'the error names the contested check'


@pytest.mark.unit
class TestRegisteredChecks:
    def test_registered_checks_with_the_header_alias_declared_holds_the_frontmatter_check_once(self) -> None:
        #: Given
        alias = 'header'

        #: When
        names = [check.name for check in registered_checks()]

        #: Then
        assert names.count(FRONTMATTER_CHECK.name) == 1, 'the frontmatter check is registered once'
        assert alias not in names, 'the alias is a second command name, not a second check a bare run would repeat'
