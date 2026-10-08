"""Render the rulebook: one page per rule from its class's docstring, and the listing of every rule.

Pure: the registry arrives as a value and each function returns the text a command prints or a recipe writes, so
nothing here reads the disk or writes to a stream. A page is what `docs/rulebook/` holds and what `lorecraft rule
<rule>` prints, from the one function, `render_page`, so a user without this repository reads the same text.

A page is the docstring's sections, in the order the docstring writes them, under a title and a summary. What the
declaration states, the code, the release it is stable since and the alias codes, is the page's
frontmatter. Nothing is written by hand. The renderer checks no section: a docstring that lacks one renders a page
without it. The pages are generated output, kept current by `gen-check`, and no specification governs them.
"""

import inspect
import json
from dataclasses import dataclass
from typing import Final, assert_never

from lorecraft.rules.declaration import EngineCondition, RemovedRule, Rule, RuleDeclaration
from lorecraft.rules.registry import Registry

_SECTION_MARKER: Final[str] = '## '
"""What starts a section in a docstring, as it would in a page."""

_FENCE: Final[str] = '```'
"""What opens and closes a fenced block, inside which a line starting with a section marker is example text."""

_ATTRIBUTES_HEADER: Final[str] = 'Attributes:'
"""The line that ends the sections: the fields below it are documented for the maintainer, not for a user."""


@dataclass(frozen=True, slots=True)
class _DocSection:
    """One section of a rule's docstring.

    Attributes:
        heading: The section's heading text, without its marker, such as `What it does`.
        body: The section's text below the heading, as the docstring wrote it, without surrounding blank lines.
    """

    heading: str
    body: str


@dataclass(frozen=True, slots=True)
class _RuleDoc:
    """A rule's docstring, split into the parts a page is made of.

    Attributes:
        summary: The condition the rule reports: the docstring's first paragraph on one line.
        sections: The sections that follow, in the order the docstring writes them.
    """

    summary: str
    sections: tuple[_DocSection, ...]


def _parse_docstring(docstring: str | None) -> _RuleDoc:
    """Split a docstring into its summary and its `##` sections, leaving out the `Attributes:` block.

    A line that starts a section is one outside a fenced block: an example may show a document with headings of its
    own. Text between the summary and the first section belongs to neither, and is left out.

    Args:
        docstring: The docstring of a rule's class, or None when it has none.
    """
    lines = inspect.cleandoc(docstring or '').splitlines()
    summary_lines: list[str] = []
    for line in lines:
        if not line.strip():
            break
        summary_lines.append(line.strip())

    sections: list[_DocSection] = []
    heading: str | None = None
    body_lines: list[str] = []
    in_fence = False
    for line in lines[len(summary_lines) :]:
        if line.startswith(_FENCE):
            in_fence = not in_fence
        if not in_fence:
            if line == _ATTRIBUTES_HEADER:
                break
            if line.startswith(_SECTION_MARKER):
                if heading is not None:
                    sections.append(_DocSection(heading, '\n'.join(body_lines).strip()))
                heading = line.removeprefix(_SECTION_MARKER).strip()
                body_lines = []
                continue
        body_lines.append(line)
    if heading is not None:
        sections.append(_DocSection(heading, '\n'.join(body_lines).strip()))
    return _RuleDoc(' '.join(summary_lines), tuple(sections))


def page_name(declaration: RuleDeclaration) -> str:
    """The name of a rule's page without `.md`: its code, then its name, such as `OUT004-empty-section`.

    The code comes first so a listing of the directory sorts in code order, and the name is what the file says the
    rule is. It is the page's frontmatter `name` too.

    Args:
        declaration: The rule, removed rule or engine condition.
    """
    return f'{declaration.CODE}-{declaration.NAME}'


def render_page(declaration: RuleDeclaration) -> str:
    """The page of a rule, a removed rule or an engine condition, as the file in `docs/rulebook/` holds it.

    What the declaration states is the page's frontmatter; the body is the title, the summary and the docstring's
    sections.

    Args:
        declaration: The rule, removed rule or engine condition.
    """
    doc = _parse_docstring(declaration.__doc__)
    frontmatter = '\n'.join(['---', *_frontmatter_lines(declaration, doc.summary), '---'])
    blocks = [frontmatter, f'# {declaration.NAME} ({declaration.CODE})', doc.summary]
    for section in doc.sections:
        blocks.append(f'{_SECTION_MARKER}{section.heading}\n\n{section.body}')
    return '\n\n'.join(blocks) + '\n'


def render_listing(registry: Registry) -> str:
    """One line per rule, removed rules and engine conditions included, in code order.

    A line is the code, the name, the level and the condition the rule reports. A removed rule shows `removed` in
    place of a level, and an engine condition the `error` it is always reported at, as it has no level.

    Args:
        registry: The registry to list.
    """
    rows: list[tuple[str, str, str, str]] = []
    for declaration in registry.rules:
        summary = _parse_docstring(declaration.__doc__).summary
        rows.append((str(declaration.CODE), str(declaration.NAME), _level_column(declaration), summary))
    code_width = max((len(code) for code, _, _, _ in rows), default=0)
    name_width = max((len(name) for _, name, _, _ in rows), default=0)
    level_width = max((len(level) for _, _, level, _ in rows), default=0)
    return '\n'.join(
        f'{code:<{code_width}}  {name:<{name_width}}  {level:<{level_width}}  {summary}'
        for code, name, level, summary in rows
    )


def _level_column(declaration: RuleDeclaration) -> str:
    """The word the listing shows for a declaration in place of a level.

    Args:
        declaration: The rule, removed rule or engine condition.
    """
    # A `match` class pattern tests an instance, not a class, so the branch on a declaration's kind is an
    # `issubclass` chain, closed by `assert_never` as the registry's own is.
    if issubclass(declaration, Rule):
        return declaration.LEVEL.value
    elif issubclass(declaration, RemovedRule):
        return 'removed'
    elif issubclass(declaration, EngineCondition):
        return declaration.SEVERITY.value
    else:
        assert_never(declaration)


def _frontmatter_lines(declaration: RuleDeclaration, summary: str) -> list[str]:
    """The `key: value` lines of a page's frontmatter: its name and description, then what the declaration states.

    Every string is written as a JSON string, which is a valid YAML double-quoted scalar, so a summary with a quote or
    a backslash needs no escaping of its own.

    Args:
        declaration: The rule, removed rule or engine condition.
        summary: The docstring's first paragraph, which is the description once its final period is dropped.
    """
    lines = [
        f'name: {_quoted(page_name(declaration))}',
        f'description: {_quoted(summary.removesuffix("."))}',
        f'code: {_quoted(str(declaration.CODE))}',
    ]
    # An `issubclass` chain, closed by `assert_never`, for the reason `_level_column` gives.
    if issubclass(declaration, Rule):
        lines.append(f'since: {_quoted(str(declaration.SINCE))}')
        if declaration.ALIASES:
            aliases = ', '.join(_quoted(f'{alias} ({alias.linter})') for alias in declaration.ALIASES)
            lines.append(f'aliases: [{aliases}]')
    elif issubclass(declaration, RemovedRule):
        lines.append(f'removed-in: {_quoted(str(declaration.REMOVED_IN))}')
        if declaration.REPLACED_BY is not None:
            lines.append(f'replaced-by: {_quoted(str(declaration.REPLACED_BY))}')
    elif issubclass(declaration, EngineCondition):
        lines.append(f'since: {_quoted(str(declaration.SINCE))}')
    else:
        assert_never(declaration)
    return lines


def _quoted(text: str) -> str:
    """The text as a YAML double-quoted scalar.

    Args:
        text: The text to quote.
    """
    return json.dumps(text, ensure_ascii=False)
