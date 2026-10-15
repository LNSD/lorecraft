"""The JSON Schema vocabulary and the one seam to the third-party validator."""

from .dialect import DIALECT
from .json_type import JsonType, JsonTypes
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
    keyword_of,
)

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
    'keyword_of',
]
