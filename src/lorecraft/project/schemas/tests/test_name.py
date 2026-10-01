"""Schema name parsing and formatting."""

import pytest

from lorecraft.project.aspect import AspectNamespace, InvalidAspectNamespaceCharacterError
from lorecraft.project.corpus import CorpusName

from ..name import SchemaName, parse_schema_name, schema_name_stem


@pytest.mark.unit
class TestSchemaName:
    def test_corpus_tuple_has_corpus_stem(self) -> None:
        #: Given
        name: SchemaName = (CorpusName.parse('code'),)

        #: When
        stem = schema_name_stem(name)

        #: Then
        assert stem == 'code', 'a corpus schema has no namespace segment'

    def test_parse_treats_everything_after_corpus_as_namespace(self) -> None:
        #: Given
        stem = 'code-python-errors'

        #: When
        name = parse_schema_name(stem)

        #: Then
        assert name == (CorpusName.parse('code'), AspectNamespace.parse('python-errors')), (
            'the full suffix is one namespace'
        )

    def test_namespace_tuple_joins_kebab_namespace(self) -> None:
        #: Given
        name: SchemaName = (
            CorpusName.parse('code'),
            AspectNamespace.parse('python-errors-handling'),
        )

        #: When
        stem = schema_name_stem(name)

        #: Then
        assert stem == 'code-python-errors-handling', 'the namespace follows the corpus'

    def test_parse_with_underscore_in_namespace_raises_namespace_error(self) -> None:
        #: Given
        stem = 'code-python_errors_handling'

        #: When
        with pytest.raises(InvalidAspectNamespaceCharacterError) as exc_info:
            parse_schema_name(stem)

        #: Then
        assert exc_info.value.namespace == 'python_errors_handling', 'the error retains the rejected namespace'
