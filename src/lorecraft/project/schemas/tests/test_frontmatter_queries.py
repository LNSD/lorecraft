"""Project queries over frontmatter ownership and parsed skill fields."""

import pytest

from lib.primitives import StructurePrimitives
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.item import DocumentOrigin, WrongItemTypeError

from ..frontmatter_queries import owner_of_frontmatter


@pytest.mark.unit
class TestOwnerOfFrontmatter:
    def test_owner_of_frontmatter_with_a_document_without_corpus_structure_raises_wrong_item_type_error(self) -> None:
        #: Given
        expected_error = WrongItemTypeError
        primitives = StructurePrimitives(
            (),
            origin_value=DocumentOrigin(),
            name=AspectFilename.parse('guide'),
            corpus=CorpusName.parse('guide'),
        )

        #: When
        with pytest.raises(expected_error) as exc_info:
            owner_of_frontmatter(primitives)

        #: Then
        assert exc_info.type is expected_error, 'a document without a structure spec raises the exact typed error'
