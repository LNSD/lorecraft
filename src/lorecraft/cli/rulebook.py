"""Render the rulebook: one page per rule from its class's docstring, and the listing of every rule.

Pure: the registry arrives as a value and each function returns the text a command prints, so nothing here reads the
disk or writes to a stream. `lorecraft rule <rule>` prints a page from the one function, `render_page`, so a user
without this repository reads the same text as anyone.

A page is the docstring's sections, in the order the docstring writes them, under a title and a list of what the
declaration states: the code, the group, the level, the release it is stable since, where it comes from and where it
is declared. Nothing is written by hand. The renderer checks no section: a docstring that lacks one renders a page
without it.
"""

import inspect
import json
from dataclasses import dataclass, fields
from typing import Final, assert_never

from lorecraft.core.path import RootRelativePath
from lorecraft.rules.declaration import EngineCondition, RemovedRule, Rule, RuleDeclaration
from lorecraft.rules.registry import Registry

_SOURCE_URL: Final[str] = 'https://github.com/LNSD/lorecraft/blob/main/src/'
"""Where the package's source is published, so a page links a rule's module for a reader without the repository."""

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


def render_page(declaration: RuleDeclaration, registry: Registry) -> str:
    """The page of a rule, a removed rule or an engine condition, as the file in `docs/rulebook/` holds it.

    Args:
        declaration: The rule, removed rule or engine condition.
        registry: The registry that holds it, which names the rule a removed rule links to.
    """
    doc = _parse_docstring(declaration.__doc__)
    # A JSON string is a valid YAML double-quoted scalar, so a summary with a quote or a backslash needs no escaping
    # of its own.
    description = json.dumps(doc.summary.removesuffix('.'), ensure_ascii=False)
    blocks = [
        f'---\nname: "{page_name(declaration)}"\ndescription: {description}\n---',
        f'# {declaration.NAME} ({declaration.CODE})',
        doc.summary,
        '\n'.join(_facts(declaration, registry)),
    ]
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


def _facts(declaration: RuleDeclaration, registry: Registry) -> list[str]:
    """The bullets a page lists under its summary: what the declaration states, by the kind of declaration.

    Args:
        declaration: The rule, removed rule or engine condition.
        registry: The registry that holds it.
    """
    group = declaration.CODE.group
    # An `issubclass` chain, closed by `assert_never`, for the reason `_level_column` gives.
    facts = [f'- **Code:** `{declaration.CODE}`', f'- **Group:** `{group.prefix}`, {group.title}']
    if issubclass(declaration, Rule):
        facts.append(f'- **Default level:** `{declaration.LEVEL.value}`')
        facts.append(f'- **Stable since:** `{declaration.SINCE}`')
        facts.append(f'- **Origin:** {_origin(declaration)}')
        if declaration.ALIASES:
            aliases = ', '.join(f'`{alias}` of {alias.linter}' for alias in declaration.ALIASES)
            facts.append(f'- **Aliases:** {aliases}')
    elif issubclass(declaration, RemovedRule):
        facts.append(f'- **Removed in:** `{declaration.REMOVED_IN}`')
        facts.append(f'- **Replaced by:** {_replacement(declaration, registry)}')
    elif issubclass(declaration, EngineCondition):
        facts.append(f'- **Severity:** `{declaration.SEVERITY.value}`, always: it has no level')
        facts.append(f'- **Stable since:** `{declaration.SINCE}`')
        facts.append("- **Origin:** Lorecraft's engine, which reports it before any rule judges the subject")
    else:
        assert_never(declaration)
    facts.append(f'- **Declared in:** {_source_link(declaration)}')
    return facts


def _origin(rule_class: type[Rule]) -> str:
    """Where a rule's condition is stated: a specification of the repository, or Lorecraft itself.

    The type of the rule's `spec` field says it, so no second declaration can disagree: a rule whose every occurrence
    names the specification file that states it is declared `RootRelativePath`, a rule the package states `None`, and
    a rule that is either, as one over a document and a skill, keeps the type of the base.

    Args:
        rule_class: The rule in service.
    """
    spec_type = next(field.type for field in fields(rule_class) if field.name == 'spec')
    if spec_type is RootRelativePath:
        return 'a specification of the repository states it, and the diagnostic points at the file that does'
    if spec_type is None:
        return 'Lorecraft states it, as no specification of the repository does'
    return 'a specification of the repository states it, or Lorecraft does where none does'


def _replacement(removed_rule: type[RemovedRule], registry: Registry) -> str:
    """What replaced a removed rule: a link to the page of the rule, or that nothing did.

    Args:
        removed_rule: The removed rule.
        registry: The registry that holds the rule that replaced it.
    """
    replaced_by = removed_rule.REPLACED_BY
    if replaced_by is None:
        return 'nothing'
    replacement = registry.find(str(replaced_by))
    if replacement is None:
        # The registry rejects, as it loads, a removed rule replaced by a code no rule declares.
        raise AssertionError(
            f'unreachable: {removed_rule.__qualname__} is replaced by {replaced_by}, which no rule declares'
        )
    return f'[`{replaced_by}`]({page_name(replacement)}.md)'


def _source_link(declaration: RuleDeclaration) -> str:
    """A link to the module that declares the rule, at the published source.

    Args:
        declaration: The rule, removed rule or engine condition.
    """
    path = declaration.__module__.replace('.', '/') + '.py'
    return f'[`src/{path}`]({_SOURCE_URL}{path})'
