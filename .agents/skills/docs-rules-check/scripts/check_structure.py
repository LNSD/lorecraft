#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml>=6.0,<7",
#   "typer>=0.12,<1",
#   "pydantic>=2.7,<3",
#   "markdown-it-py>=3.0,<4",
#   "mdit-py-plugins>=0.4,<0.5",
# ]
# ///
"""Check docs/ section structure against the structure specs in docs/__meta__/.

This is a vendored copy, kept as-is until the lorecraft library implements the check and
the skill calls that instead.

Covers the mechanical half of a specification's Document Structure section: which
sections a document must carry, which its type forbids, the order of the ones whose
order is fixed, and whether any section was left empty. Judgment calls stay with
/docs-rules-check - whether a section says what it should, whether a cross-reference
points in an allowed direction.

This script owns no rules. It reads a document's structure and applies the spec, which
is where every rule lives.


## The spec dialect

An outline is a *sequence*, and JSON Schema cannot state ordering over a sequence whose
length varies: `prefixItems` pins a fixed tuple and nothing more. So a structure spec is
not JSON Schema. It is the small dialect below, whose models are the authority for it:

    {
      "spec": "code.md §5",
      "description": "what this file governs",
      "title": {"count": 1, "first": true},
      "empty_sections": "forbidden",
      "outline": [
        {"section": "Table of Contents", "optional": true},
        {"any": true},
        {"section": "Checklist"},
        {"section": "References", "optional": true},
        {"section": "External References", "optional": true}
      ],
      "forbidden": ["Changelog"]
    }

The fields, and what each decides:

- `spec` names the prose this file is the machine-checkable half of. Every finding the
  file raises quotes it, so a reader is sent to the rule rather than to the JSON.
- `description` says what the file governs, and what it layers with, for whoever opens
  it. Nothing but a person reads it.
- `title` states how many H1 titles a document carries (`count`, at least one) and
  whether one opens it ahead of every section (`first`).
- `empty_sections`, set to `"forbidden"`, reports any section left without content. It is
  what keeps a required section from being satisfied by a bare heading. Omitting the field
  leaves empty sections unchecked, and `"forbidden"` is the only value it takes.
- `outline` is the section order and `forbidden` the sections barred outright. Both are
  described below.

`outline` is the document's skeleton: **a corpus has one section order, and this is it.**
The entries are matched against the document's sections left to right.

- `{"section": ...}` names a section and fixes its position relative to every other name
  in the outline. It is required unless `optional` says otherwise.
- `{"any": true}` matches a run of any length of sections the outline does *not* name -
  the places where a document is free to add its own. The run stops at any named section,
  which is what pins a name to its position wherever in the document it turns up, and
  what lets the walk decide every document without backtracking.

`forbidden` names sections that must not appear at all. A forbidden section has no
position, which is why it is stated here rather than in the outline.

A spec must state at least one rule, name no section twice, forbid nothing its own
outline requires, and never place two `any` runs side by side. Each of those is an error
in the spec rather than in a document, and a spec is read once for a whole corpus, so it
is refused when the spec is loaded rather than reported against whichever document
happened to be checked first.


## Layering

A spec states rules; it asks no questions about the document it is applied to. Where a
corpus's documents answer differently - a `principle` document carries External
References, a `meta` document must not - that is **another spec layered on this one**,
never a condition inside it.

A document's own path and `type` name the layers that govern it:

    docs/<corpus>/<prefix>-<rest>.md, type: <type>
      -> docs/__meta__/<corpus>.structure.json          (required; else the corpus is ungoverned)
      -> docs/__meta__/<corpus>-<prefix>.structure.json (optional, for that filename prefix)
      -> docs/__meta__/<corpus>.<type>.structure.json   (optional, for that frontmatter type)

Each layer is a whole spec and each is applied on its own, so a layer states only what it
adds, no layer has to restate what a broader one already said, and none can escape one
either. An absent layer adds nothing.

Headings come from a CommonMark parse rather than a line scan, so a `#` comment inside a
fenced code block is not mistaken for a heading, and only the document's own top-level
headings count: one quoted in a blockquote or nested in a list item illustrates a document
rather than sectioning this one.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from enum import Enum
from functools import cache
from itertools import pairwise
from pathlib import Path
from typing import Annotated, Any, Literal

import typer
import yaml
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode
from mdit_py_plugins.front_matter import front_matter_plugin
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

META_DIR = Path('docs/__meta__')
DOCS_DIR = Path('docs')

SECTION_LEVEL = 2


class Section(BaseModel):
    """One named section, and whether the document must carry it."""

    model_config = ConfigDict(extra='forbid')

    section: str
    optional: bool = False


class AnySections(BaseModel):
    """A run, of any length, of sections the outline does not name."""

    model_config = ConfigDict(extra='forbid')

    any: Literal[True]


class Title(BaseModel):
    """How many H1 titles a document carries, and whether one opens it."""

    model_config = ConfigDict(extra='forbid')

    count: int = Field(ge=1)
    first: bool


class StructureSpec(BaseModel):
    """The rules one `<stem>.structure.json` states. See this module's docstring."""

    model_config = ConfigDict(extra='forbid')

    spec: str
    description: str = ''
    title: Title | None = None
    empty_sections: Literal['forbidden'] | None = None
    outline: list[Section | AnySections] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def reject_unusable_spec(self) -> StructureSpec:
        """Refuse a spec that checks nothing, contradicts itself, or repeats itself."""
        if not (self.title or self.empty_sections or self.outline or self.forbidden):
            raise ValueError('states no rule, so it would check nothing')

        named = [entry.section for entry in self.outline if isinstance(entry, Section)]
        repeated = sorted({name for name in named if named.count(name) > 1})
        if repeated:
            raise ValueError(f'names sections more than once in the outline: {repeated}')

        contradicted = sorted(set(named) & set(self.forbidden))
        if contradicted:
            raise ValueError(f'forbids sections its own outline requires: {contradicted}')

        for earlier, later in pairwise(self.outline):
            # Two runs side by side match exactly what one run matches, so a spec written
            # this way means something other than what it says.
            if isinstance(earlier, AnySections) and isinstance(later, AnySections):
                raise ValueError('places two `any` runs side by side, which match as one')

        return self


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    message: str

    def as_text(self) -> str:
        return f'{self.path}:{self.line}: [{self.rule}] {self.message}'

    def as_dict(self) -> dict[str, str | int]:
        return {'file': self.path, 'line': self.line, 'rule': self.rule, 'message': self.message}


@dataclass(frozen=True)
class Heading:
    level: int
    text: str
    line: int
    empty: bool


def heading_text(heading: SyntaxTreeNode) -> str:
    """The heading's text with inline markup stripped, so `Checklist` matches Checklist."""
    inline = heading.children[0]
    return ''.join(child.content for child in inline.children if child.type in ('text', 'code_inline'))


def parse(text: str) -> tuple[dict[str, Any], list[Heading]]:
    """Return the document's frontmatter mapping and its top-level headings."""
    md = MarkdownIt('commonmark').use(front_matter_plugin)
    # The root's own children, not every heading in the stream: a heading quoted in a
    # blockquote or nested in a list item illustrates a document, it does not section
    # this one.
    blocks = list(SyntaxTreeNode(md.parse(text)).children)

    frontmatter: dict[str, Any] = {}
    for node in blocks:
        if node.type == 'front_matter':
            loaded = yaml.safe_load(node.content)
            frontmatter = loaded if isinstance(loaded, dict) else {}
            break

    headings: list[Heading] = []
    for index, node in enumerate(blocks):
        if node.type != 'heading':
            continue
        level = int(node.tag[1])
        # A section is empty when nothing follows it before the next sibling or
        # ancestor heading, the end of the document included. A deeper heading is a
        # subsection, and its content counts as this section's own.
        following = blocks[index + 1 :]
        empty = not following or (following[0].type == 'heading' and int(following[0].tag[1]) <= level)
        line = node.map[0] + 1 if node.map else 1
        headings.append(Heading(level=level, text=heading_text(node), line=line, empty=empty))
    return frontmatter, headings


def spec_paths(root: Path, doc: Path, doc_type: str) -> list[Path]:
    """Resolve the specs that govern a document: the corpus file, then the layers on it.

    The corpus file comes first and the rest narrow it. Each layer is optional, and an
    absent one simply adds nothing.
    """
    corpus = doc.relative_to(root / DOCS_DIR).parts[0]
    prefix = doc.stem.split('-')[0]

    base = root / META_DIR / f'{corpus}.structure.json'
    layers = [
        root / META_DIR / f'{corpus}-{prefix}.structure.json',
        root / META_DIR / f'{corpus}.{doc_type}.structure.json' if doc_type else None,
    ]
    return [base, *(path for path in layers if path is not None and path.exists())]


class MalformedSpec(Exception):
    """A structure spec is not a valid spec, so it decides nothing."""


@cache
def load_spec(path: Path) -> StructureSpec:
    """Load a structure spec, refusing one that checks nothing or that nothing can satisfy."""
    try:
        return StructureSpec.model_validate_json(path.read_text(encoding='utf-8'))
    except ValidationError as err:
        raise MalformedSpec(f'{path}: {err}') from err


def check_title(spec: StructureSpec, headings: list[Heading]) -> list[tuple[int, str, str]]:
    """Check the document's H1 title against the spec. Returns (line, rule, message) triples."""
    if spec.title is None:
        return []

    findings = []
    titles = [h for h in headings if h.level == 1]
    if len(titles) != spec.title.count:
        findings.append((1, 'structure.title', f'expected {spec.title.count} H1 title, found {len(titles)}'))
    if spec.title.first and not (headings and headings[0].level == 1):
        findings.append((1, 'structure.title', 'the H1 title comes before any section'))
    return findings


def check_empty(spec: StructureSpec, headings: list[Heading]) -> list[tuple[int, str, str]]:
    """Report every empty section, where the spec forbids them."""
    if spec.empty_sections != 'forbidden':
        return []
    return [
        (h.line, 'structure.empty', f'section `{h.text}` is empty; omit it rather than leaving it empty')
        for h in headings
        if h.empty
    ]


def check_forbidden(spec: StructureSpec, sections: list[Heading]) -> list[tuple[int, str, str]]:
    """Report every section this spec forbids outright."""
    lines = {h.text: h.line for h in sections}
    return [
        (lines[name], 'structure.forbidden', f'section `{name}` is forbidden here')
        for name in spec.forbidden
        if name in lines
    ]


def check_outline(spec: StructureSpec, sections: list[Heading]) -> list[tuple[int, str, str]]:
    """Match the outline against the document's sections, left to right.

    One finding at most: past the first divergence every later entry is measured against
    sections it was never meant to match, and those cascades say nothing.
    """
    if not spec.outline:
        return []

    named = {entry.section for entry in spec.outline if isinstance(entry, Section)}
    at = 0  # the first section not yet accounted for

    for entry in spec.outline:
        if isinstance(entry, AnySections):
            # The run stops at a section the outline names: that section belongs to the
            # entry naming it, wherever in the outline that entry falls.
            while at < len(sections) and sections[at].text not in named:
                at += 1
            continue

        if at < len(sections) and sections[at].text == entry.section:
            at += 1
            continue
        if entry.optional:
            continue

        if at < len(sections):
            found = sections[at]
            return [
                (
                    found.line,
                    'structure.outline',
                    f'expected section `{entry.section}`, found `{found.text}`',
                )
            ]
        return [(1, 'structure.outline', f'missing required section `{entry.section}`')]

    if at < len(sections):
        left = sections[at]
        # A leftover the outline names is a section written out of turn; one it does not
        # name is a section written past the point where the document should have ended.
        message = (
            f'section `{left.text}` is out of order'
            if left.text in named
            else f'unexpected section `{left.text}`; the outline ends before it'
        )
        return [(left.line, 'structure.outline', message)]
    return []


def validate(root: Path, doc: Path) -> tuple[list[Finding], bool]:
    """Check one document. Returns its findings and whether a spec governed it."""
    rel = doc.relative_to(root).as_posix()

    if not doc.is_relative_to(root / DOCS_DIR):
        return [], False

    frontmatter, headings = parse(doc.read_text(encoding='utf-8'))
    doc_type = str(frontmatter.get('type', ''))
    sections = [h for h in headings if h.level == SECTION_LEVEL]

    paths = spec_paths(root, doc, doc_type)
    if not paths[0].exists():
        return [], False

    findings: list[Finding] = []
    for path in paths:
        spec = load_spec(path)
        raised = [
            *check_title(spec, headings),
            *check_empty(spec, headings),
            *check_forbidden(spec, sections),
            *check_outline(spec, sections),
        ]
        findings.extend(Finding(rel, line, rule, f'{message} (per {spec.spec})') for line, rule, message in raised)

    return sorted(findings, key=lambda f: (f.line, f.rule)), True


def collect(root: Path, paths: list[Path]) -> list[Path]:
    if paths:
        return [path.resolve() for path in paths]
    return sorted(
        p
        for p in (root / DOCS_DIR).rglob('*.md')
        if p.relative_to(root / DOCS_DIR).parts[0] != '__meta__' and len(p.relative_to(root / DOCS_DIR).parts) > 1
    )


def find_root(start: Path) -> Path | None:
    """Walk up from `start` for the repository root, the directory holding docs/__meta__/."""
    for candidate in (start, *start.parents):
        if (candidate / META_DIR).is_dir():
            return candidate
    return None


USAGE_EXAMPLES = """\
\b
examples:
  check_structure.py                            check every governed corpus under docs/
  check_structure.py docs/code/python-typing.md check named documents
  check_structure.py --format json              machine-readable findings
\b
exit codes:
  0  no findings
  1  findings printed to stdout
  2  bad usage: a path that does not exist, or is outside the repository
"""


class OutputFormat(str, Enum):
    """How findings are reported."""

    text = 'text'
    json = 'json'


# Click rewraps help text, and rich's formatter styles it. Neither preserves the columns
# above, so the plain formatter is selected and each block is marked pre-formatted with a
# `\b` line, which is how Click is told to leave a paragraph as written.
app = typer.Typer(add_completion=False, rich_markup_mode=None)


@app.command(epilog=USAGE_EXAMPLES)
def main(
    paths: Annotated[
        list[Path] | None,
        typer.Argument(help='documents to check; defaults to every corpus under docs/'),
    ] = None,
    root: Annotated[
        Path | None,
        typer.Option(help='repository root (default: found by walking up from the current directory)'),
    ] = None,
    output_format: Annotated[
        OutputFormat,
        typer.Option('--format', help='output format'),
    ] = OutputFormat.text,
) -> None:
    """Check docs/ section structure against the structure specs in docs/__meta__/."""
    # Resolving the root by walking up keeps the script runnable from any directory,
    # which matters because a skill may invoke it from its own directory rather than
    # from the repository root.
    if root is not None:
        root = root.resolve()
        if not (root / META_DIR).is_dir():
            print(f'--root {root} has no {META_DIR}/; give the repository root', file=sys.stderr)
            raise typer.Exit(code=2)
    else:
        found = find_root(Path.cwd())
        if found is None:
            print(
                f'no {META_DIR}/ in the current directory or any parent; run from inside the repository or pass --root',
                file=sys.stderr,
            )
            raise typer.Exit(code=2)
        root = found

    docs = collect(root, paths or [])

    findings: list[Finding] = []
    ungoverned: list[str] = []
    for doc in docs:
        if not doc.exists():
            print(f'no such file: {doc}', file=sys.stderr)
            raise typer.Exit(code=2)
        if not doc.is_relative_to(root):
            print(f'{doc} is outside the repository at {root}', file=sys.stderr)
            raise typer.Exit(code=2)
        try:
            doc_findings, governed = validate(root, doc)
        except MalformedSpec as err:
            print(f'malformed structure spec: {err}', file=sys.stderr)
            raise typer.Exit(code=2) from err
        findings.extend(doc_findings)
        if not governed:
            ungoverned.append(doc.relative_to(root).as_posix())

    if output_format is OutputFormat.json:
        print(
            json.dumps(
                {
                    'checked': len(docs),
                    'findings': [f.as_dict() for f in findings],
                    'ungoverned': ungoverned,
                },
                indent=2,
            )
        )
    else:
        for finding in findings:
            print(finding.as_text())
        for path in ungoverned:
            print(f'{path}:1: [corpus.ungoverned] no structure spec for this corpus; structure unvalidated')
        print(f'checked {len(docs)} file(s), {len(findings)} finding(s)', file=sys.stderr)

    raise typer.Exit(code=1 if findings else 0)


if __name__ == '__main__':
    app()
