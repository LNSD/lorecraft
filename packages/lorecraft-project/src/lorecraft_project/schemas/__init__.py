"""Specification filenames and stems, the decoded schemas, the header and structure aspects, and the repository that
reads them."""

from .budget import BudgetSchema
from .header import HeaderAspect, HeaderSchema, InvalidHeaderSchemaError
from .name import SchemaName, parse_schema_name, schema_name_stem
from .repo import (
    GetBudgetSchemaError,
    GetHeaderSchemaError,
    GetStructureSchemaError,
    ListCorpusSchemasError,
    ListSchemasError,
    ListSpecsError,
    Repository,
)
from .spec_file import (
    InvalidSpecStemError,
    NotASpecFileError,
    NotASpecStemError,
    SpecAspect,
    SpecFile,
    SpecFilenameError,
    UnknownSpecAspectError,
    parse_spec_file,
    schema_filename,
)
from .structure import (
    AnySections,
    InvalidStructureSchemaError,
    OutlineEntry,
    SectionEntry,
    StructureAspect,
    StructureSchema,
    TitleRule,
)
from .structure_file import StructureFile

__all__ = [
    'SchemaName',
    'parse_schema_name',
    'schema_name_stem',
    'SpecAspect',
    'SpecFile',
    'parse_spec_file',
    'schema_filename',
    'SpecFilenameError',
    'NotASpecFileError',
    'UnknownSpecAspectError',
    'NotASpecStemError',
    'InvalidSpecStemError',
    'HeaderSchema',
    'HeaderAspect',
    'InvalidHeaderSchemaError',
    'BudgetSchema',
    'StructureSchema',
    'StructureAspect',
    'TitleRule',
    'StructureFile',
    'OutlineEntry',
    'SectionEntry',
    'AnySections',
    'InvalidStructureSchemaError',
    'GetBudgetSchemaError',
    'GetHeaderSchemaError',
    'GetStructureSchemaError',
    'ListCorpusSchemasError',
    'ListSchemasError',
    'ListSpecsError',
    'Repository',
]
