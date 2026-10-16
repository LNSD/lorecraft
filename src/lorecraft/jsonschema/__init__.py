"""The JSON Schema vocabulary and the one seam to the third-party validator."""

from .dialect import DIALECT
from .json_type import JsonType, JsonTypes
from .schema_check import find_same_instance_ref_cycle, is_resolved_inside, iter_schemas
from .schema_inspection import (
    SchemaCheckFailure,
    SchemaHasIdentifier,
    SchemaHasSameInstanceReferenceCycle,
    SchemaHasUnresolvableReference,
    SchemaMetaError,
    SchemaUsesForeignDialect,
    check_schema,
)
from .schema_keyword import (
    AdditionalPropertiesKeyword,
    ConstKeyword,
    DependentRequiredKeyword,
    EnumKeyword,
    Keyword,
    MaxPropertiesKeyword,
    MinPropertiesKeyword,
    OtherKeyword,
    PatternKeyword,
    RequiredKeyword,
    TypeKeyword,
    UnevaluatedPropertiesKeyword,
)
from .validation import best_violation, validate
from .violation import Violation

__all__: list[str] = [
    'DIALECT',
    'JsonType',
    'JsonTypes',
    'AdditionalPropertiesKeyword',
    'ConstKeyword',
    'DependentRequiredKeyword',
    'EnumKeyword',
    'Keyword',
    'MaxPropertiesKeyword',
    'MinPropertiesKeyword',
    'OtherKeyword',
    'PatternKeyword',
    'RequiredKeyword',
    'TypeKeyword',
    'UnevaluatedPropertiesKeyword',
    'SchemaCheckFailure',
    'SchemaHasIdentifier',
    'SchemaHasSameInstanceReferenceCycle',
    'SchemaHasUnresolvableReference',
    'SchemaMetaError',
    'SchemaUsesForeignDialect',
    'Violation',
    'check_schema',
    'validate',
    'best_violation',
    'find_same_instance_ref_cycle',
    'is_resolved_inside',
    'iter_schemas',
]
