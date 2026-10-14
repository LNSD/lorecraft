"""Read specification files from one directory through the filesystem boundary.

Every path the repository takes or returns is root-relative: the specification directory is joined to the
workspace root only inside `FileSystem`. The repository reads; the text it returns is typed as
read and nothing more. Whether a structure specification states usable rules, its frontmatter schema included, is
proved by `StructureSpec.parse`; which documents a specification governs is decided above the repository.

Nothing here logs: the command that loads the model catches every `Error` that escapes it and reports it,
so every handler below re-raises without logging.
"""

from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.vfs import (
    FILE_READ_FAILURES,
    EntryKind,
    FileReadFailure,
    FileSystem,
    TextDecodeError,
    UnrecordedFileError,
)

from .name import SpecName
from .spec_file import StructureSpecFile
from .structure import StructureSchema


class StructureSchemaReadError(Error):
    """A structure schema the model names cannot be read.

    Attributes:
        name: The specification name whose structure file was being read.
        source: The failure to read the file, or to decode its bytes as UTF-8.
    """

    name: SpecName
    source: FileReadFailure | UnrecordedFileError | TextDecodeError

    def __init__(self, name: SpecName, *, source: FileReadFailure | UnrecordedFileError | TextDecodeError) -> None:
        self.name = name
        self.source = source
        super().__init__(f'cannot read the structure schema {name}')
        self.__cause__ = source


class Repository:
    """Expose specification files under one directory by specification name."""

    def __init__(self, fs: FileSystem, specs_dir: RootRelativePath) -> None:
        """Remember the seam and the root-relative directory; performs no I/O.

        Args:
            fs: Filesystem boundary every read goes through.
            specs_dir: Root-relative directory holding the specification files. It need not exist.
        """
        self._fs = fs
        self._specs_dir = specs_dir

    def list_spec_paths(self) -> list[RootRelativePath]:
        """List the root-relative path of every regular file in the directory, sorted by name.

        Nothing is parsed here: the caller parses each path with `parse_spec_file`, and decides what to do
        with a file whose name is not a specification filename. A missing directory lists as nothing.

        Raises:
            DirListError: If the directory exists but cannot be listed, on disk.
            RecordedDirListError: If a snapshot recorded that the directory could not be listed.
        """
        # A failure to list is the listing's own, with the directory as its path: this layer adds nothing to it.
        entries = self._fs.list_dir(self._specs_dir)
        return [self._specs_dir / entry.name for entry in entries if entry.kind is EntryKind.FILE]

    def get_structure_schema(self, file: StructureSpecFile) -> StructureSchema:
        """Read one structure schema's text, undecoded.

        `StructureSpec.parse` deserializes and validates it in one step, so the JSON is read once, by the
        model that states its shape.

        Args:
            file: The structure file to read, `<name>.spec.json` or the legacy `<name>.structure.json`; the caller
                decides which of the two a specification name is read from.

        Raises:
            StructureSchemaReadError: If the file cannot be read, or its bytes are not UTF-8.
        """
        try:
            return StructureSchema(self._fs.read_text(file.path))
        except (*FILE_READ_FAILURES, UnrecordedFileError, TextDecodeError) as exc:
            raise StructureSchemaReadError(file.name, source=exc) from exc
