"""Specification name parsing and formatting."""

import pytest

from lorecraft.project.aspect import AspectNamespace, InvalidAspectNamespaceCharacterError
from lorecraft.project.corpus import CorpusName

from ..name import CorpusSpecName, NamespaceSpecName, parse_spec_name


@pytest.mark.unit
class TestSpecName:
    def test_str_of_corpus_spec_name_is_the_corpus(self) -> None:
        #: Given
        name = CorpusSpecName(CorpusName.parse('code'))

        #: When
        text = str(name)

        #: Then
        assert text == 'code', 'a corpus spec name has no namespace segment'

    def test_parse_without_hyphen_gives_corpus_spec_name(self) -> None:
        #: Given
        raw = 'code'

        #: When
        name = parse_spec_name(raw)

        #: Then
        assert name == CorpusSpecName(CorpusName.parse('code')), 'a name with no hyphen names a corpus spec'

    def test_parse_treats_everything_after_corpus_as_namespace(self) -> None:
        #: Given
        raw = 'code-python-errors'

        #: When
        name = parse_spec_name(raw)

        #: Then
        assert name == NamespaceSpecName(CorpusName.parse('code'), AspectNamespace.parse('python-errors')), (
            'the full suffix is one namespace'
        )

    def test_str_of_namespace_spec_name_joins_kebab_namespace(self) -> None:
        #: Given
        name = NamespaceSpecName(CorpusName.parse('code'), AspectNamespace.parse('python-errors-handling'))

        #: When
        text = str(name)

        #: Then
        assert text == 'code-python-errors-handling', 'the namespace follows the corpus'

    def test_parse_with_underscore_in_namespace_raises_namespace_error(self) -> None:
        #: Given
        raw = 'code-python_errors_handling'

        #: When
        with pytest.raises(InvalidAspectNamespaceCharacterError) as exc_info:
            parse_spec_name(raw)

        #: Then
        assert exc_info.value.namespace == 'python_errors_handling', 'the error retains the rejected namespace'
