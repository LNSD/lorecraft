"""The frontmatter node of a document's parse tree: the decoded YAML mapping and where each key sits.

A document's frontmatter is a ``---`` delimited block on its first lines. Finding the block is the Markdown
parser's job (see ``document``); decoding it is this module's. Parsing has exactly four outcomes, one type each:
no block, a block that is not YAML, a block that is YAML but not a mapping, and a mapping. Every outcome is a
value, never an exception, because a broken block is a fact about the document that a check reports, not a
failure of the parse.
"""

from dataclasses import dataclass
from typing import Final

import yaml
from yaml.reader import ReaderError

from .position import LineNumber

_FIRST_BLOCK_LINE: Final[int] = 2
"""The document line the block's first YAML line sits on: the opening delimiter is always line 1."""


@dataclass(frozen=True, slots=True)
class FrontmatterKey:
    """One top-level key of a frontmatter mapping and the line it is written on.

    Attributes:
        name: The key as YAML decoded it.
        line: The document line the key starts on.
    """

    name: str
    line: LineNumber


@dataclass(frozen=True, slots=True)
class Frontmatter:
    """A frontmatter block that decoded to a YAML mapping.

    Frozen for equality only: ``data`` is a dict, so an instance is not hashable and must not be put in a set
    or used as a key. The parse tree is shared by every check that reads the document, so no check mutates
    ``data``.

    Attributes:
        data: The decoded mapping, exactly as ``yaml.safe_load`` returns it.
        keys: Every top-level key written as a plain string, in document order, with its line.
    """

    data: dict[object, object]
    keys: tuple[FrontmatterKey, ...]

    def key_line(self, name: str) -> LineNumber | None:
        """The line the first top-level key called ``name`` is written on, or ``None`` when there is none."""
        for key in self.keys:
            if key.name == name:
                return key.line
        return None


@dataclass(frozen=True, slots=True)
class MissingFrontmatter:
    """The document does not open with a ``---`` line, or the block is never closed by one."""


@dataclass(frozen=True, slots=True)
class InvalidYamlFrontmatter:
    """The block is there but is not valid YAML.

    A value, compared by value, so it holds the parser's facts rather than the parser's exception, which compares
    by identity.

    Attributes:
        problem: What the YAML parser found wrong, in its own words, such as ``mapping values are not allowed here``.
        line: The document line the problem is on, or None when the parser does not say.
    """

    problem: str
    line: LineNumber | None


@dataclass(frozen=True, slots=True)
class NonMappingFrontmatter:
    """The block is valid YAML, but it decodes to something other than a mapping, such as a list or nothing."""


type FrontmatterNode = Frontmatter | MissingFrontmatter | InvalidYamlFrontmatter | NonMappingFrontmatter
"""Every outcome of parsing a document's frontmatter."""


def decode_frontmatter(block: str) -> FrontmatterNode:
    """Decode the YAML between a document's ``---`` delimiters into its node. Pure: raises nothing.

    Never ``MissingFrontmatter``: whether a block exists is decided before this is called.

    Args:
        block: The lines between the delimiters, line endings kept; the first of them is document line 2.
    """
    # `yaml.safe_load` composes a node tree and then constructs the value from it. The two steps run here
    # apart, on one loader, because the node tree is what records the line each key is written on.
    try:
        # The loader checks every character as it is built, so a control character fails here, not in the parse.
        loader = yaml.SafeLoader(block)
    except ReaderError as exc:
        line = LineNumber(block.count('\n', 0, exc.position) + _FIRST_BLOCK_LINE)
        return InvalidYamlFrontmatter(problem=exc.reason, line=line)
    try:
        node = loader.get_single_node()
        data: object = None if node is None else loader.construct_document(node)
    except yaml.MarkedYAMLError as exc:
        return _invalid_yaml(exc)
    finally:
        loader.dispose()

    if not isinstance(node, yaml.MappingNode) or not isinstance(data, dict):
        return NonMappingFrontmatter()
    return Frontmatter(data=data, keys=_keys(node))


def _invalid_yaml(error: yaml.MarkedYAMLError) -> InvalidYamlFrontmatter:
    """The parser's facts about a block that does not parse: its problem, and the line it marked."""
    # The parser names the problem, or, for a few errors, only the construct it was reading when it stopped.
    problem = error.problem or error.context or 'the block is not valid YAML'
    mark = error.problem_mark or error.context_mark
    if mark is None:
        return InvalidYamlFrontmatter(problem=problem, line=None)
    # The mark counts lines from 0 within the block; the block starts on document line 2.
    return InvalidYamlFrontmatter(problem=problem, line=LineNumber(mark.line + _FIRST_BLOCK_LINE))


def _keys(mapping: yaml.MappingNode) -> tuple[FrontmatterKey, ...]:
    """Every top-level key of the mapping written as a plain string, with its document line.

    A key the mapping spells some other way, such as a list or a number, has no name a check could ask for,
    so it is left out.
    """
    keys: list[FrontmatterKey] = []
    for key_node, _value_node in mapping.value:
        if not isinstance(key_node, yaml.ScalarNode) or key_node.tag != 'tag:yaml.org,2002:str':
            continue
        # The mark counts lines from 0 within the block; the block starts on document line 2.
        line = LineNumber(key_node.start_mark.line + _FIRST_BLOCK_LINE)
        keys.append(FrontmatterKey(name=key_node.value, line=line))
    return tuple(keys)
