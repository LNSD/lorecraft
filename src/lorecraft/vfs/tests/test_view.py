"""The classification of an operating system refusal by its ``errno``.

The integration tier raises the refusals a permission bit or a missing path produces on a real tree; the
rest of the ``errno`` values ``OsRefusal.from_error`` names are built here as the ``OSError`` the operating system
would raise.
"""

import errno

import pytest

from ..view import OsRefusal


@pytest.mark.unit
class TestOsRefusalFromError:
    def test_from_error_with_an_operation_not_permitted_returns_permission_denied(self) -> None:
        #: Given
        error = OSError(errno.EPERM, 'Operation not permitted')

        #: When
        refusal = OsRefusal.from_error(error)

        #: Then
        assert refusal is OsRefusal.PERMISSION_DENIED, f'EPERM is a permission refusal, like EACCES, got {refusal}'

    def test_from_error_with_a_component_that_is_not_a_directory_returns_not_a_directory(self) -> None:
        #: Given
        error = OSError(errno.ENOTDIR, 'Not a directory')

        #: When
        refusal = OsRefusal.from_error(error)

        #: Then
        assert refusal is OsRefusal.NOT_A_DIRECTORY, f'ENOTDIR is classified as such, got {refusal}'

    def test_from_error_with_a_directory_where_a_file_was_expected_returns_is_a_directory(self) -> None:
        #: Given
        error = OSError(errno.EISDIR, 'Is a directory')

        #: When
        refusal = OsRefusal.from_error(error)

        #: Then
        assert refusal is OsRefusal.IS_A_DIRECTORY, f'EISDIR is classified as such, got {refusal}'

    def test_from_error_with_an_errno_the_enum_does_not_name_returns_other(self) -> None:
        #: Given
        error = OSError(errno.ELOOP, 'Too many levels of symbolic links')

        #: When
        refusal = OsRefusal.from_error(error)

        #: Then
        assert refusal is OsRefusal.OTHER, f'ELOOP has no value of its own, so it is OTHER, got {refusal}'
