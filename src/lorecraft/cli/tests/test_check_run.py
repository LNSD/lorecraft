"""The check registry a bare ``lorecraft check`` reads: what a check module's registration may and may not do.

The registry is process-wide, so these cases register only the header check itself, or a rival under its name
that is refused before it is stored; a new name would join every later bare run in the same process.
"""

import pytest

from lorecraft.checks import run_header

from ..check_run import DocumentCheck, DuplicateCheckError, register_check, registered_checks
from ..commands.check.header import HEADER_CHECK


@pytest.mark.unit
class TestRegisterCheck:
    def test_register_check_with_the_same_check_again_keeps_one_entry(self) -> None:
        #: Given
        before = registered_checks()

        #: When
        returned = register_check(HEADER_CHECK)

        #: Then
        assert returned is HEADER_CHECK, 'registration returns the check unchanged, so it can be bound to a name'
        assert registered_checks() == before, 'registering the same check twice is a no-op'

    def test_register_check_with_a_different_check_under_a_taken_name_raises_duplicate_check_error(self) -> None:
        #: Given
        rival = DocumentCheck(name=HEADER_CHECK.name, run=run_header, ungoverned='another message')

        #: When
        with pytest.raises(DuplicateCheckError) as exc_info:
            register_check(rival)

        #: Then
        assert HEADER_CHECK.name in str(exc_info.value), 'the error names the contested check'
