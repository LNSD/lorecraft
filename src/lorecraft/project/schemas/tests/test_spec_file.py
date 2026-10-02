"""The specification filename grammar: parsing a filename into its specification name and file type, and back."""

from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectNamespace, InvalidAspectNamespaceCharacterError
from lorecraft.project.corpus import CorpusName, InvalidCorpusNameCharacterError

from ..name import CorpusSpecName, NamespaceSpecName
from ..spec_file import (
    DottedSpecStemError,
    InvalidSpecStemError,
    NotASpecFileError,
    NotASpecStemError,
    SpecFile,
    SpecFileType,
    UnknownSpecFileTypeError,
    parse_spec_file,
    spec_filename,
)

META: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__')
CODE: Final[CorpusName] = CorpusName.parse('code')


@pytest.mark.unit
class TestParseSpecFile:
    def test_parse_spec_file_with_a_corpus_prose_file_returns_a_prose_spec_file(self) -> None:
        #: Given
        path = META / 'code.md'

        #: When
        spec_file = parse_spec_file(path)

        #: Then
        assert spec_file == SpecFile(path=path, name=CorpusSpecName(CODE), type=SpecFileType.PROSE), (
            'code.md parses into the code corpus spec name and the prose file type'
        )

    def test_parse_spec_file_with_a_corpus_structure_file_returns_a_structure_spec_file(self) -> None:
        #: Given
        path = META / 'code.structure.json'

        #: When
        spec_file = parse_spec_file(path)

        #: Then
        assert spec_file == SpecFile(path=path, name=CorpusSpecName(CODE), type=SpecFileType.STRUCTURE), (
            'code.structure.json parses into the code corpus spec name and the structure file type'
        )

    def test_parse_spec_file_with_a_header_file_raises_unknown_spec_file_type_error(self) -> None:
        #: Given
        # the frontmatter schema moved into the structure specification, so no file type claims *.header.json
        path = META / 'code.header.json'

        #: When
        with pytest.raises(UnknownSpecFileTypeError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.token == 'header', 'no file type claims *.header.json'

    def test_parse_spec_file_with_a_nested_namespace_structure_file_returns_a_structure_spec_file(self) -> None:
        #: Given
        path = META / 'code-python-errors.structure.json'

        #: When
        spec_file = parse_spec_file(path)

        #: Then
        assert spec_file == SpecFile(
            path=path, name=NamespaceSpecName(CODE, AspectNamespace.parse('python-errors')), type=SpecFileType.STRUCTURE
        ), 'code-python-errors.structure.json parses into the code corpus, one python-errors namespace and structure'

    def test_parse_spec_file_with_a_dotted_structure_stem_raises_dotted_spec_stem_error(self) -> None:
        #: Given
        path = META / 'feat.component.structure.json'

        #: When
        with pytest.raises(DottedSpecStemError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, 'feat.component is not a specification name; the error names the file'
        assert exc_info.value.stem == 'feat.component', 'the error holds the stem with the dot'
        assert 'feat.component' in str(exc_info.value), f'the message names the dotted stem, got {exc_info.value}'

    def test_parse_spec_file_with_dotted_prose_raises_dotted_spec_stem_error(self) -> None:
        #: Given
        path = META / 'feat.feature.md'

        #: When
        with pytest.raises(DottedSpecStemError) as exc_info:
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
        assert str(path) in str(exc_info.value), f'the message names the rejected file, got {exc_info.value}'

    def test_parse_spec_file_with_json_without_a_token_raises_not_a_spec_file_error(self) -> None:
        #: Given
        path = META / 'notes.json'

        #: When
        with pytest.raises(NotASpecFileError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, (
            'a .json file without a token before .json is not a specification file; the error names notes.json'
        )

    def test_parse_spec_file_with_json_without_a_stem_raises_not_a_spec_file_error(self) -> None:
        #: Given
        path = META / '.structure.json'

        #: When
        with pytest.raises(NotASpecFileError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, (
            'a bare .structure.json has no stem, so it is not a specification file; the error names it'
        )

    def test_parse_spec_file_with_json_with_an_empty_token_raises_not_a_spec_file_error(self) -> None:
        #: Given
        path = META / 'code..json'

        #: When
        with pytest.raises(NotASpecFileError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, (
            'code..json has an empty token before .json, so it is not a specification file; the error names it'
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

    def test_parse_spec_file_with_an_unknown_token_raises_unknown_spec_file_type_error(self) -> None:
        #: Given
        path = META / 'code.headers.json'

        #: When
        with pytest.raises(UnknownSpecFileTypeError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, 'no file type claims *.headers.json; the error names code.headers.json'
        assert str(path) in str(exc_info.value), f'the message names the rejected file, got {exc_info.value}'

    def test_parse_spec_file_with_a_budget_file_raises_unknown_spec_file_type_error(self) -> None:
        #: Given
        # word caps are part of the structure dialect, so no file type claims *.budget.json
        path = META / 'code.budget.json'

        #: When
        with pytest.raises(UnknownSpecFileTypeError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.token == 'budget', 'no file type claims *.budget.json'

    def test_parse_spec_file_with_prose_at_a_non_stem_raises_not_a_spec_stem_error(self) -> None:
        #: Given
        path = META / 'README.md'

        #: When
        with pytest.raises(NotASpecStemError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, (
            'prose not at a specification name is not a specification; the error names README.md'
        )
        assert isinstance(exc_info.value.source, InvalidCorpusNameCharacterError), (
            f'README is not a corpus name for its uppercase letters, got {type(exc_info.value.source).__name__}'
        )
        assert str(path) in str(exc_info.value), f'the message names the prose file, got {exc_info.value}'

    def test_parse_spec_file_with_json_at_a_non_stem_raises_invalid_spec_stem_error(self) -> None:
        #: Given
        path = META / 'README.structure.json'

        #: When
        with pytest.raises(InvalidSpecStemError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, (
            'a structure file must be at a valid specification name; the error names README.structure.json'
        )
        assert isinstance(exc_info.value.source, InvalidCorpusNameCharacterError), (
            f'README is not a corpus name for its uppercase letters, got {type(exc_info.value.source).__name__}'
        )
        assert str(path) in str(exc_info.value), f'the message names the rejected file, got {exc_info.value}'

    def test_parse_spec_file_with_an_uppercase_namespace_raises_invalid_spec_stem_error(self) -> None:
        #: Given
        path = META / 'code-Python.md'

        #: When
        with pytest.raises(InvalidSpecStemError) as exc_info:
            parse_spec_file(path)

        #: Then
        assert exc_info.value.path == path, (
            'a namespace with an uppercase letter is not a valid specification name; the error names code-Python.md'
        )
        assert isinstance(exc_info.value.source, InvalidAspectNamespaceCharacterError), (
            f'Python is not a namespace for its uppercase letter, got {type(exc_info.value.source).__name__}'
        )


@pytest.mark.unit
class TestSpecFilenames:
    def test_spec_filename_with_a_namespace_spec_name_writes_what_parse_reads(self) -> None:
        #: Given
        name = NamespaceSpecName(CODE, AspectNamespace.parse('python'))

        #: When
        filename = spec_filename(name, SpecFileType.STRUCTURE)

        #: Then
        assert filename == 'code-python.structure.json', 'the name is followed by what *.structure.json claims'

    def test_spec_filename_with_the_prose_type_writes_the_markdown_file_at_the_name(self) -> None:
        #: Given
        name = NamespaceSpecName(CODE, AspectNamespace.parse('python'))

        #: When
        filename = spec_filename(name, SpecFileType.PROSE)

        #: Then
        assert filename == 'code-python.md', 'the name is followed by what *.md claims'
