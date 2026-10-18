"""Project queries over frontmatter ownership and parsed skill fields."""

import pytest

from lib.primitives import StructurePrimitives
from lorecraft.project.item import DocumentOrigin, WrongItemKindError

from ..frontmatter_queries import frontmatter_owner_query


@pytest.mark.unit
class TestFrontmatterOwnerQuery:
    def test_frontmatter_owner_query_with_a_document_without_corpus_structure_raises_typed_error(self) -> None:
        #: Given
        primitives = StructurePrimitives(
            (),
            origin_value=DocumentOrigin(expected_name='guide', corpus='guide', schema_paths=()),
        )

        #: When / Then
        with pytest.raises(
            WrongItemKindError, match='expected a document whose corpus states a structure specification'
        ):
            frontmatter_owner_query(primitives)
