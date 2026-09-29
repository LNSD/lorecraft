"""The specification filename grammar: parsing a filename into its stem and aspect, and writing it back."""

from typing import Final

import pytest

from lorecraft_project.aspect import AspectNamespace
from lorecraft_project.corpus import CorpusName
from lorecraft_vfs import RootRelativePath

from ..name import SchemaName
from ..spec_file import (
    InvalidSpecStemError,
    NotASpecFileError,
    NotASpecStemError,
    SpecAspect,
    SpecFile,
    UnknownSpecAspectError,
    parse_spec_file,
    schema_filename,
)

META: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__')
CODE: Final[CorpusName] = CorpusName.parse('code')


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

    def test_parse_spec_file_with_a_nested_namespace_structure_file_returns_a_structure_spec_file(self) -> None:
        #: Given
        path = META / 'code-python-errors.structure.json'

        #: When
        spec_file = parse_spec_file(path)

        #: Then
        assert spec_file == SpecFile(
            path=path, name=(CODE, AspectNamespace.parse('python-errors')), aspect=SpecAspect.STRUCTURE
        ), 'code-python-errors.structure.json parses into the code corpus, one python-errors namespace and structure'

    def test_parse_spec_file_with_a_dotted_structure_stem_raises_invalid_spec_stem_error(self) -> None:
        #: Given
        path = META / 'feat.component.structure.json'

        #: When
        with pytest.raises(InvalidSpecStemError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, 'feat.component is not a stem; the error names the file'
        assert 'dot' in exc_info.value.detail, 'the detail says the stem holds a dot'

    def test_parse_spec_file_with_a_dotted_header_stem_raises_invalid_spec_stem_error(self) -> None:
        #: Given
        path = META / 'feat.feature.header.json'

        #: When
        with pytest.raises(InvalidSpecStemError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, 'a dot in the stem is rejected whatever the aspect'

    def test_parse_spec_file_with_dotted_prose_raises_invalid_spec_stem_error(self) -> None:
        #: Given
        path = META / 'feat.feature.md'

        #: When
        with pytest.raises(InvalidSpecStemError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, 'prose at a dotted stem is a misnaming, not prose kept beside the specs'

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

    def test_parse_spec_file_with_a_budget_file_raises_unknown_spec_aspect_error(self) -> None:
        #: Given
        # word caps are part of the structure dialect, so budget is no longer an aspect of its own
        path = META / 'code.budget.json'

        #: When
        with pytest.raises(UnknownSpecAspectError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.token == 'budget', 'budget is not one of the aspect tokens'

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


@pytest.mark.unit
class TestSpecFilenames:
    def test_schema_filename_with_a_namespace_stem_writes_what_parse_reads(self) -> None:
        #: Given
        name: SchemaName = (CODE, AspectNamespace.parse('python'))

        #: When
        filename = schema_filename(name, SpecAspect.STRUCTURE)

        #: Then
        assert filename == 'code-python.structure.json', 'the stem is followed by the aspect token and .json'
