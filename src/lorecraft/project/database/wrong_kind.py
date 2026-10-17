"""The defect of asking one kind of item for a fact only another kind has."""

from lorecraft.project.item import MarkdownItemRef


class WrongItemKindError(TypeError):
    """A fact of one kind of item was asked of another, which a rule that applies to its kind never does."""

    def __init__(self, ref: MarkdownItemRef, asked: str) -> None:
        super().__init__(f'{ref.path} is not {asked}')
