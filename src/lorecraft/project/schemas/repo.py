"""Read specification files from one directory through the filesystem boundary.

Every path the repository takes or returns is root-relative: the specification directory is joined to the
workspace root only inside ``FileSystem``. The repository reads; the text it returns is typed as
read and nothing more. Whether a structure specification states usable rules, its frontmatter schema included, is
proved by ``StructureAspect.parse``; which documents a specification governs is decided above the repository.

Nothing here logs: the command that loads the model catches every ``Error`` that escapes it and reports it,
so every handler below re-raises without logging.
"""

from lorecraft.core.error import Error
from lorecraft.core.path import RootRelativePath
from lorecraft.project.corpus import CorpusName
from lorecraft.vfs import DirListError, EntryKind, FileReadError, FileSystem, UnrecordedFileError

from .name import SchemaName, schema_name_stem
from .spec_file import (
    DottedSpecStemError,
    InvalidSpecStemError,
    NotASpecFileError,
    NotASpecStemError,
    SpecAspect,
    SpecFile,
    UnknownSpecAspectError,
    parse_spec_file,
    schema_filename,
)
from .structure import StructureSchema


class CorpusSchemasListError(Error):
    """The schemas of one corpus cannot be listed, because the specification directory cannot be.

    Attributes:
        corpus: The corpus whose schemas were being listed.
        source: The failure to list the specification directory.
    """

    corpus: CorpusName
    source: DirListError

    def __init__(self, corpus: CorpusName, *, source: DirListError) -> None:
        self.corpus = corpus
        self.source = source
        super().__init__(f'cannot list the schemas of corpus {corpus}')
        self.__cause__ = source


class StructureSchemaReadError(Error):
    """A structure schema the model names cannot be read.

    Attributes:
        name: The schema whose structure file was being read.
        source: The failure to read the file.
    """

    name: SchemaName
    source: FileReadError | UnrecordedFileError

    def __init__(self, name: SchemaName, *, source: FileReadError | UnrecordedFileError) -> None:
        self.name = name
        self.source = source
        super().__init__(f'cannot read the structure schema {schema_name_stem(name)}')
        self.__cause__ = source


class Repository:
    """Expose specification files under one directory by schema name."""

    def __init__(self, fs: FileSystem, specs_dir: RootRelativePath) -> None:
        """Remember the seam and the root-relative directory; performs no I/O."""
        self._fs = fs
        self._specs_dir = specs_dir

    def list_spec_paths(self) -> list[RootRelativePath]:
        """List the root-relative path of every regular file in the directory, sorted by name.

        Nothing is parsed here: the caller parses each path with ``parse_spec_file``, and decides what to do
        with a file whose name is not a specification filename. A missing directory lists as nothing.

        Raises:
            DirListError: If the directory exists but cannot be listed.
        """
        # A failure to list is the listing's own, with the directory as its path: this layer adds nothing to it.
        entries = self._fs.list_dir(self._specs_dir)
        return [self._specs_dir / entry.name for entry in entries if entry.kind is EntryKind.FILE]

    def list_schemas(self) -> list[SpecFile]:
        """List the JSON schema files, every aspect and stem form, in stable name order.

        A file whose name does not parse is left out. A missing directory lists as nothing.

        Raises:
            DirListError: If the directory exists but cannot be listed.
        """
        return self._schema_files()

    def list_schemas_by_corpus(self, corpus: CorpusName) -> list[SpecFile]:
        """List the JSON schema files whose stem belongs to one corpus, in stable name order.

        A missing directory lists as nothing.

        Raises:
            CorpusSchemasListError: If the directory exists but cannot be listed.
        """
        try:
            files = self._schema_files()
        except DirListError as exc:
            raise CorpusSchemasListError(corpus, source=exc) from exc
        return [schema for schema in files if schema.corpus == corpus]

    def get_structure_schema(self, name: SchemaName) -> StructureSchema:
        """Read one structure schema's text, undecoded: ``StructureAspect.parse`` deserializes and validates it in
        one step, so the JSON is read once, by the model that states its shape.

        Raises:
            StructureSchemaReadError: If the file cannot be read.
        """
        path = self._specs_dir / schema_filename(name, SpecAspect.STRUCTURE)
        try:
            return StructureSchema(self._fs.read_text(path))
        except (FileReadError, UnrecordedFileError) as exc:
            raise StructureSchemaReadError(name, source=exc) from exc

    def _schema_files(self) -> list[SpecFile]:
        """Parse the JSON schema files in name order; the seam already sorts its entries.

        Raises:
            DirListError: If the directory exists but cannot be listed.
        """
        schemas: list[SpecFile] = []
        for entry in self._fs.list_dir(self._specs_dir):
            if entry.kind is not EntryKind.FILE:
                continue
            try:
                spec_file = parse_spec_file(self._specs_dir / entry.name)
            except (
                NotASpecFileError,
                UnknownSpecAspectError,
                NotASpecStemError,
                DottedSpecStemError,
                InvalidSpecStemError,
            ):
                # Not a specification filename: a listing leaves it out.
                continue
            if spec_file.aspect is not None:
                schemas.append(spec_file)
        return schemas
