"""The specification filename grammar: parsing a filename into its stem and aspect, and writing it back."""

from typing import Final

import pytest

from lorecraft_project.aspect import AspectName, AspectNameError, AspectNamespace
from lorecraft_project.corpus import CorpusName
from lorecraft_vfs import RootRelativePath

from ..name import SchemaName, TypeSelectorName
from ..spec_file import (
    InvalidSpecStemError,
    NotASpecFileError,
    NotASpecStemError,
    SpecAspect,
    SpecFile,
    TypedAspectUnsupportedError,
    TypeSelectorFile,
    UnknownSpecAspectError,
    parse_spec_file,
    schema_filename,
    type_selector_filename,
)

META: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__')
CODE: Final[CorpusName] = CorpusName.parse('code')
FEAT: Final[CorpusName] = CorpusName.parse('feat')


@pytest.mark.unit
class TestParseSpecFile:
    def test_parse_spec_file_with_a_corpus_prose_file_returns_a_spec_file_without_aspect(self) -> None:
        #: Given
        path = META / 'code.md'

        #: When
        spec_file = parse_spec_file(path)

        #: Then
        assert spec_file == SpecFile(path=path, name=(CODE,), aspect=None), (
            'code.md parses into the code corpus stem with no aspect'
        )

    def test_parse_spec_file_with_a_corpus_header_file_returns_a_header_spec_file(self) -> None:
        #: Given
        path = META / 'code.header.json'

        #: When
        spec_file = parse_spec_file(path)

        #: Then
        assert spec_file == SpecFile(path=path, name=(CODE,), aspect=SpecAspect.HEADER), (
            'code.header.json parses into the code corpus stem and the header aspect'
        )

    def test_parse_spec_file_with_a_nested_namespace_budget_file_returns_a_budget_spec_file(self) -> None:
        #: Given
        path = META / 'code-python-errors.budget.json'

        #: When
        spec_file = parse_spec_file(path)

        #: Then
        assert spec_file == SpecFile(
            path=path, name=(CODE, AspectNamespace.parse('python-errors')), aspect=SpecAspect.BUDGET
        ), 'code-python-errors.budget.json parses into the code corpus, one python-errors namespace and budget'

    def test_parse_spec_file_with_a_dotted_structure_stem_returns_a_type_selector_file(self) -> None:
        #: Given
        path = META / 'feat.component.structure.json'

        #: When
        spec_file = parse_spec_file(path)

        #: Then
        assert spec_file == TypeSelectorFile(path=path, name=TypeSelectorName(FEAT, AspectName.parse('component'))), (
            'a <corpus>.<type> stem is a type selector'
        )

    def test_parse_spec_file_with_another_suffix_raises_not_a_spec_file_error(self) -> None:
        #: Given
        path = META / 'notes.txt'

        #: When
        with pytest.raises(NotASpecFileError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, 'a .txt file is not a specification file; the error names notes.txt'

    def test_parse_spec_file_with_json_without_an_aspect_token_raises_not_a_spec_file_error(self) -> None:
        #: Given
        path = META / 'notes.json'

        #: When
        with pytest.raises(NotASpecFileError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, (
            'a .json file without an aspect token is not a specification file; the error names notes.json'
        )

    def test_parse_spec_file_with_prose_without_a_stem_raises_not_a_spec_file_error(self) -> None:
        #: Given
        path = META / '.md'

        #: When
        with pytest.raises(NotASpecFileError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, (
            'a bare .md has no stem, so it is not a specification file; the error names .md'
        )

    def test_parse_spec_file_with_an_unknown_aspect_token_raises_unknown_spec_aspect_error(self) -> None:
        #: Given
        path = META / 'code.headers.json'

        #: When
        with pytest.raises(UnknownSpecAspectError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, 'headers is not one of the aspect tokens; the error names code.headers.json'

    def test_parse_spec_file_with_a_typed_header_raises_typed_aspect_unsupported_error(self) -> None:
        #: Given
        path = META / 'feat.feature.header.json'

        #: When
        with pytest.raises(TypedAspectUnsupportedError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, (
            'a type selector carries no header aspect; the error names feat.feature.header.json'
        )

    def test_parse_spec_file_with_typed_prose_raises_typed_aspect_unsupported_error(self) -> None:
        #: Given
        path = META / 'feat.feature.md'

        #: When
        with pytest.raises(TypedAspectUnsupportedError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, 'a type selector carries no prose; the error names feat.feature.md'

    def test_parse_spec_file_with_a_typed_budget_and_invalid_tokens_raises_typed_aspect_unsupported_error(self) -> None:
        #: Given
        path = META / 'Bad.feature.budget.json'

        #: When
        with pytest.raises(TypedAspectUnsupportedError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, (
            'the typed-aspect rule is checked before the stem tokens; the error names Bad.feature.budget.json'
        )

    def test_parse_spec_file_with_prose_at_a_non_stem_raises_not_a_spec_stem_error(self) -> None:
        #: Given
        path = META / 'README.md'

        #: When
        with pytest.raises(NotASpecStemError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, (
            'prose whose name is not a stem is not a specification; the error names README.md'
        )

    def test_parse_spec_file_with_json_at_a_non_stem_raises_invalid_spec_stem_error(self) -> None:
        #: Given
        path = META / 'README.header.json'

        #: When
        with pytest.raises(InvalidSpecStemError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, (
            'an aspect file must be named after a valid stem; the error names README.header.json'
        )

    def test_parse_spec_file_with_an_uppercase_namespace_raises_invalid_spec_stem_error(self) -> None:
        #: Given
        path = META / 'code-Python.md'

        #: When
        with pytest.raises(InvalidSpecStemError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, (
            'a namespace with an uppercase letter is not a valid stem; the error names code-Python.md'
        )

    def test_parse_spec_file_with_two_type_tokens_raises_invalid_spec_stem_error(self) -> None:
        #: Given
        path = META / 'feat.a.b.structure.json'

        #: When
        with pytest.raises(InvalidSpecStemError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, (
            'a type selector has exactly one type token; the error names feat.a.b.structure.json'
        )

    def test_parse_spec_file_with_an_invalid_type_token_carries_the_parser_message_as_detail(self) -> None:
        #: Given
        path = META / 'feat.Feature.structure.json'

        #: When
        with pytest.raises(InvalidSpecStemError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert isinstance(exc_info.value.__cause__, AspectNameError), 'the type parser error is chained'
        assert exc_info.value.detail == str(exc_info.value.__cause__), 'the detail is the type parser message'


@pytest.mark.unit
class TestSpecFilenames:
    def test_schema_filename_with_a_namespace_stem_writes_what_parse_reads(self) -> None:
        #: Given
        name: SchemaName = (CODE, AspectNamespace.parse('python'))

        #: When
        filename = schema_filename(name, SpecAspect.STRUCTURE)

        #: Then
        assert filename == 'code-python.structure.json', 'the stem is followed by the aspect token and .json'

    def test_type_selector_filename_writes_a_structure_file(self) -> None:
        #: Given
        name = TypeSelectorName(FEAT, AspectName.parse('component'))

        #: When
        filename = type_selector_filename(name)

        #: Then
        assert filename == 'feat.component.structure.json', 'a type selector carries the structure aspect only'


@pytest.mark.unit
class TestTypeSelectorName:
    def test_parse_with_a_dotted_stem_splits_at_the_first_dot(self) -> None:
        #: Given
        stem = 'feat.component'

        #: When
        name = TypeSelectorName.parse(stem)

        #: Then
        assert name == TypeSelectorName(FEAT, AspectName.parse('component')), 'corpus before the dot, type after'

    def test_parse_with_no_dot_raises_aspect_name_error(self) -> None:
        #: Given
        stem = 'feat'

        #: When
        with pytest.raises(AspectNameError) as exc_info:
            TypeSelectorName.parse(stem)

        #: Then
        assert exc_info.value.name == '', 'a stem with no dot has an empty type token'
