"""Specification filenames and stems, the decoded schemas, the header aspect and the repository that reads them."""

from .budget import BudgetSchema
from .header import HeaderAspect, HeaderSchema, InvalidHeaderSchemaError
from .name import SchemaName, TypeSelectorName, parse_schema_name, schema_name_stem
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
    TypedAspectUnsupportedError,
    TypeSelectorFile,
    UnknownSpecAspectError,
    parse_spec_file,
    schema_filename,
    type_selector_filename,
)
from .structure import StructureSchema

__all__ = [
    'SchemaName',
    'parse_schema_name',
    'schema_name_stem',
    'TypeSelectorName',
    'SpecAspect',
    'SpecFile',
    'TypeSelectorFile',
    'parse_spec_file',
    'schema_filename',
    'type_selector_filename',
    'SpecFilenameError',
    'NotASpecFileError',
    'UnknownSpecAspectError',
    'TypedAspectUnsupportedError',
    'NotASpecStemError',
    'InvalidSpecStemError',
    'HeaderSchema',
    'HeaderAspect',
    'InvalidHeaderSchemaError',
    'BudgetSchema',
    'StructureSchema',
    'GetBudgetSchemaError',
    'GetHeaderSchemaError',
    'GetStructureSchemaError',
    'ListCorpusSchemasError',
    'ListSchemasError',
    'ListSpecsError',
    'Repository',
]
