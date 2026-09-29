"""The header aspect: its construction is the Draft 2020-12 well-formedness check."""

from typing import Final

import pytest

from lorecraft.vfs import RootRelativePath

from ..header import HeaderAspect, HeaderSchema, InvalidHeaderSchemaError

SCHEMA_PATH: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.header.json')


@pytest.mark.unit
class TestHeaderAspect:
    def test_construction_with_a_well_formed_schema_keeps_it(self) -> None:
        #: Given
        schema = HeaderSchema({'type': 'object', 'required': ['name']})

        #: When
        aspect = HeaderAspect(path=SCHEMA_PATH, schema=schema)

        #: Then
        assert aspect.schema == schema, 'a well-formed schema is held unchanged'

    def test_construction_with_a_malformed_schema_raises_invalid_header_schema_error(self) -> None:
        #: Given
        schema = HeaderSchema({'type': 'nonsense'})

        #: When
        with pytest.raises(InvalidHeaderSchemaError) as exc_info:
            HeaderAspect(path=SCHEMA_PATH, schema=schema)

        #: Then
        assert exc_info.value.path == SCHEMA_PATH, 'the error names the rejected schema file'
