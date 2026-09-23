#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "typer>=0.12,<1",
# ]
# ///
"""Check docs/ prose length against the budget specs in docs/__meta__/.

This is a vendored copy, kept as-is until the lorewright library implements the check and
the skill calls that instead.

Feature and rule documents are loaded into an agent's context on demand, so every word
is paid for on every task that touches the subject. A budget spec caps a document and
each of its sections in prose words; this script counts and reports what is over.

This script owns no rules. It reads a document and applies the spec, which is where
every number lives.

A document's own path names the budget spec that governs it, the same rule the other
checks follow:

    docs/<corpus>/<prefix>-<rest>.md
      -> docs/__meta__/<corpus>.budget.json          (required; else the corpus is unbudgeted)
      -> docs/__meta__/<corpus>-<prefix>.budget.json (optional overlay, replaces matching keys)


## The spec dialect

    {
      "spec": "code.md §6",
      "description": "what this file governs",
      "document": 1200,
      "sections": {"Checklist": 120, "Anti-Patterns": 400},
      "default": 300,
      "exempt": ["Table of Contents", "References"]
    }

- `document` caps the whole body, frontmatter excluded.
- `sections` caps named H2 sections, each including its H3 children.
- `default` caps every H2 section `sections` does not name. Omit it to leave them uncapped.
- `exempt` names H2 sections with no section cap. They still count toward `document`.

A word is whitespace-delimited text outside fenced code blocks and outside table rows.
Code and tables are free: they are the examples and references a document exists to hold.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

META_DIR = Path('docs/__meta__')
DOCS_DIR = Path('docs')


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


@dataclass
class Section:
    title: str
    line: int
    words: int = 0


def body_lines(text: str) -> list[tuple[int, str]]:
    """The document's lines after the frontmatter, numbered from 1 in the file."""
    lines = text.splitlines()
    start = 0
    if lines and lines[0].strip() == '---':
        for offset, line in enumerate(lines[1:], start=1):
            if line.strip() == '---':
                start = offset + 1
                break
    return [(number, line) for number, line in enumerate(lines, start=1) if number > start]


def count(text: str) -> tuple[int, list[Section]]:
    """Prose words for the whole body and per H2 section."""
    total = 0
    sections: list[Section] = []
    current: Section | None = None
    in_fence = False
    for number, line in body_lines(text):
        stripped = line.strip()
        if stripped.startswith('```') or stripped.startswith('~~~'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith('## ') and not stripped.startswith('###'):
            current = Section(stripped[3:].strip(), number)
            sections.append(current)
            continue
        if stripped.startswith('#') or stripped.startswith('|'):
            continue
        words = len(stripped.split())
        total += words
        if current is not None:
            current.words += words
    return total, sections


def budget_paths(root: Path, doc: Path) -> tuple[Path, Path | None, str]:
    corpus = doc.relative_to(root / DOCS_DIR).parts[0]
    base = root / META_DIR / f'{corpus}.budget.json'
    prefix = doc.stem.split('-')[0]
    overlay = root / META_DIR / f'{corpus}-{prefix}.budget.json'
    return base, (overlay if overlay.exists() else None), corpus


def load_spec(base: Path, overlay: Path | None) -> dict:
    spec = json.loads(base.read_text(encoding='utf-8'))
    if overlay is not None:
        for key, value in json.loads(overlay.read_text(encoding='utf-8')).items():
            if key == 'sections' and isinstance(spec.get('sections'), dict):
                spec['sections'] = {**spec['sections'], **value}
            else:
                spec[key] = value
    return spec


def validate(root: Path, doc: Path) -> tuple[list[Finding], bool]:
    """Check one document. Returns its findings and whether a budget governed it."""
    rel = doc.relative_to(root).as_posix()
    if not doc.is_relative_to(root / DOCS_DIR):
        return [], False
    base, overlay, corpus = budget_paths(root, doc)
    if not base.exists():
        return [], False

    spec = load_spec(base, overlay)
    where = f'per {base.relative_to(root).as_posix()}, {spec.get("spec", "")}'.rstrip(', ')
    total, sections = count(doc.read_text(encoding='utf-8'))
    findings: list[Finding] = []

    cap = spec.get('document')
    if isinstance(cap, int) and total > cap:
        findings.append(
            Finding(rel, 1, f'{corpus}.budget.document', f'{total} prose words; the budget is {cap} ({where})')
        )

    named = spec.get('sections', {})
    default = spec.get('default')
    exempt = set(spec.get('exempt', []))
    for section in sections:
        if section.title in exempt:
            continue
        cap = named.get(section.title, default)
        if isinstance(cap, int) and section.words > cap:
            findings.append(
                Finding(
                    rel,
                    section.line,
                    f'{corpus}.budget.section',
                    f'`{section.title}` is {section.words} prose words; the budget is {cap} ({where})',
                )
            )
    return findings, True


def collect(root: Path, paths: list[Path]) -> list[Path]:
    if paths:
        return [path.resolve() for path in paths]
    return sorted(
        p
        for p in (root / DOCS_DIR).rglob('*.md')
        if p.relative_to(root / DOCS_DIR).parts[0] != '__meta__' and len(p.relative_to(root / DOCS_DIR).parts) > 1
    )


def find_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / META_DIR).is_dir():
            return candidate
    return None


USAGE_EXAMPLES = """\
\b
examples:
  check_budget.py                            check every budgeted corpus under docs/
  check_budget.py docs/code/python-typing.md check named documents
  check_budget.py --format json              machine-readable findings
\b
exit codes:
  0  no findings
  1  findings printed to stdout
  2  bad usage: a path that does not exist, or is outside the repository
"""


class OutputFormat(str, Enum):
    text = 'text'
    json = 'json'


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
    output: Annotated[OutputFormat, typer.Option('--format', help='output format')] = OutputFormat.text,
) -> None:
    """Report documents and sections over their prose-word budget."""
    repo = root.resolve() if root else find_root(Path.cwd().resolve())
    if repo is None or not (repo / META_DIR).is_dir():
        print('error: no docs/__meta__/ found; pass --root', file=sys.stderr)
        raise typer.Exit(code=2)

    docs = collect(repo, paths or [])
    findings: list[Finding] = []
    governed = 0
    unbudgeted: set[str] = set()
    for doc in docs:
        if not doc.is_file():
            print(f'error: {doc} does not exist', file=sys.stderr)
            raise typer.Exit(code=2)
        if not doc.is_relative_to(repo):
            print(f'error: {doc} is outside the repository', file=sys.stderr)
            raise typer.Exit(code=2)
        found, was_governed = validate(repo, doc)
        if was_governed:
            governed += 1
            findings.extend(found)
        elif doc.is_relative_to(repo / DOCS_DIR):
            unbudgeted.add(doc.relative_to(repo / DOCS_DIR).parts[0])

    if output is OutputFormat.json:
        print(json.dumps([f.as_dict() for f in findings], indent=2))
    else:
        for finding in findings:
            print(finding.as_text())
        for corpus in sorted(unbudgeted):
            print(f'docs/{corpus}: [corpus.unbudgeted] no docs/__meta__/{corpus}.budget.json; not checked')
    print(f'checked {governed} file(s), {len(findings)} finding(s)', file=sys.stderr)
    raise typer.Exit(code=1 if findings else 0)


if __name__ == '__main__':
    app()
