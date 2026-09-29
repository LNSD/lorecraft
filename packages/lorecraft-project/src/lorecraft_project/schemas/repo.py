"""Read specification files from one directory through the filesystem boundary.

Every path the repository takes or returns is root-relative: the specification directory is joined to the
workspace root only inside ``FileSystem``. The repository reads and decodes; the JSON it returns is typed as
decoded and nothing more. Whether a decoded header schema is well-formed is proved by building a
``HeaderAspect`` from it, and a decoded structure specification by ``StructureAspect.parse``; which documents
a specification governs is decided above the repository.

Nothing here logs: the command that loads the model catches every ``Error`` that escapes it and reports it,
so every handler below re-raises without logging.
"""

import json

from lorecraft_core.error import Error
from lorecraft_project.corpus import CorpusName
from lorecraft_vfs import EntryKind, FileSystem, ListDirError, ReadTextError, RootRelativePath

from .header import HeaderSchema
from .name import SchemaName
from .spec_file import SpecAspect, SpecFile, SpecFilenameError, parse_spec_file, schema_filename
from .structure import StructureSchema


class ListSchemasError(Error):
    """The specification directory cannot be listed."""


class ListSpecsError(Error):
    """The specification directory cannot be listed."""


class ListCorpusSchemasError(Error):
    """Schemas for a corpus cannot be listed."""


class GetHeaderSchemaError(Error):
    """A requested header schema cannot be loaded."""


class GetStructureSchemaError(Error):
    """A requested structure schema cannot be loaded."""


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
            ListSpecsError: If the directory exists but cannot be listed.
        """
        try:
            entries = self._fs.list_dir(self._specs_dir)
        except ListDirError as exc:
            raise ListSpecsError(f'cannot list specifications in {self._specs_dir}: {exc.detail}') from exc
        return [self._specs_dir / entry.name for entry in entries if entry.kind is EntryKind.FILE]

    def list_schemas(self) -> list[SpecFile]:
        """List the JSON schema files, every aspect and stem form, in stable name order.

        A file whose name does not parse is left out. A missing directory lists as nothing.

        Raises:
            ListSchemasError: If the directory exists but cannot be listed.
        """
        try:
            return self._schema_files()
        except ListDirError as exc:
            raise ListSchemasError(f'cannot list schemas in {self._specs_dir}: {exc.detail}') from exc

    def list_schemas_by_corpus(self, corpus: CorpusName) -> list[SpecFile]:
        """List the JSON schema files whose stem belongs to one corpus, in stable name order.

        A missing directory lists as nothing.

        Raises:
            ListCorpusSchemasError: If the directory exists but cannot be listed.
        """
        try:
            files = self._schema_files()
        except ListDirError as exc:
            raise ListCorpusSchemasError(
                f'cannot list schemas for {corpus} in {self._specs_dir}: {exc.detail}'
            ) from exc
        return [schema for schema in files if schema.corpus == corpus]

    def get_header_schema(self, name: SchemaName) -> HeaderSchema:
        """Read and JSON-decode one header schema; ``HeaderAspect`` is what proves it well-formed.

        Raises:
            GetHeaderSchemaError: If the file cannot be read, is not JSON, or is not a JSON object.
        """
        path = self._specs_dir / schema_filename(name, SpecAspect.HEADER)
        try:
            text = self._fs.read_text(path)
        except ReadTextError as exc:
            raise GetHeaderSchemaError(f'cannot read schema {path}: {exc.detail}') from exc
        try:
            definition: object = json.loads(text)
        except json.JSONDecodeError as exc:
            raise GetHeaderSchemaError(f'invalid JSON in schema {path}: {exc.msg}') from exc
        if not isinstance(definition, dict):
            raise GetHeaderSchemaError(f'expected a JSON object in schema {path}')
        return HeaderSchema(definition)

    def get_structure_schema(self, name: SchemaName) -> StructureSchema:
        """Read one structure schema's text, undecoded: ``StructureAspect.parse`` deserializes and validates it in
        one step, so the JSON is read once, by the model that states its shape.

        Raises:
            GetStructureSchemaError: If the file cannot be read.
        """
        path = self._specs_dir / schema_filename(name, SpecAspect.STRUCTURE)
        try:
            return StructureSchema(self._fs.read_text(path))
        except ReadTextError as exc:
            raise GetStructureSchemaError(f'cannot read schema {path}: {exc.detail}') from exc

    def _schema_files(self) -> list[SpecFile]:
        """Parse the JSON schema files in name order; the seam already sorts its entries.

        Raises:
            ListDirError: If the directory exists but cannot be listed.
        """
        schemas: list[SpecFile] = []
        for entry in self._fs.list_dir(self._specs_dir):
            if entry.kind is not EntryKind.FILE:
                continue
            try:
                spec_file = parse_spec_file(self._specs_dir / entry.name)
            except SpecFilenameError:
                # Not a specification filename: a listing leaves it out.
                continue
            if spec_file.aspect is not None:
                schemas.append(spec_file)
        return schemas
