#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml>=6.0,<7",
#   "typer>=0.12,<1",
#   "jsonschema>=4.21,<5",
# ]
# ///
"""Check docs/ frontmatter against the JSON Schemas in docs/__meta__/.

This is a vendored copy, kept as-is until the lorecraft library implements the check and
the skill calls that instead.

Covers the mechanical half of /docs-rules-check: required fields, vocabularies,
naming patterns, and the description's trigger clause. Judgment calls stay with the
skill - whether sections appear in the order a specification demands, whether a
description is genuinely discovery-optimized, whether a cross-reference points in an
allowed direction.

A document's own path names the header schemas that govern it, the same rule the prose
specifications already follow:

    docs/<corpus>/<prefix>-<rest>.md
      -> docs/__meta__/<corpus>.header.json          (required; else the corpus is ungoverned)
      -> docs/__meta__/<corpus>-<prefix>.header.json (optional overlay, narrows the base)
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
import yaml
from jsonschema import Draft202012Validator

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


def split_frontmatter(text: str) -> tuple[str, int] | None:
    """Return the frontmatter block and the line its content starts on, or None."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        return None
    for offset, line in enumerate(lines[1:], start=1):
        if line.strip() == '---':
            return '\n'.join(lines[1:offset]), 2
    return None


def key_line(text: str, key: str) -> int:
    """Line number of a top-level frontmatter key, or 1 when it is absent."""
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip() == '---' and number > 1:
            break
        if line.startswith(f'{key}:') or line.startswith(f'"{key}":'):
            return number
    return 1


def header_paths(root: Path, doc: Path) -> tuple[Path, Path | None, str]:
    """Resolve the base header schema, the optional prefix overlay, and the corpus name."""
    corpus = doc.relative_to(root / DOCS_DIR).parts[0]
    base = root / META_DIR / f'{corpus}.header.json'
    prefix = doc.stem.split('-')[0]
    overlay = root / META_DIR / f'{corpus}-{prefix}.header.json'
    return base, (overlay if overlay.exists() else None), corpus


def validate(root: Path, doc: Path) -> tuple[list[Finding], bool]:
    """Check one document. Returns its findings and whether a schema governed it."""
    rel = doc.relative_to(root).as_posix()

    # Resolve the governing schema before reading anything: a corpus with no schema is
    # ungoverned, and reporting its documents against rules it never adopted is wrong.
    if not doc.is_relative_to(root / DOCS_DIR):
        return [], False

    base_path, overlay_path, corpus = header_paths(root, doc)
    if not base_path.exists():
        return [], False

    text = doc.read_text(encoding='utf-8')

    block = split_frontmatter(text)
    if block is None:
        return [Finding(rel, 1, 'frontmatter.missing', 'no `---` delimited frontmatter block')], True
    raw, _ = block

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as err:
        return [Finding(rel, 1, 'frontmatter.unparseable', f'frontmatter is not valid YAML: {err}')], True
    if not isinstance(data, dict):
        return [Finding(rel, 1, 'frontmatter.unparseable', 'frontmatter is not a YAML mapping')], True

    findings: list[Finding] = []

    name = data.get('name')
    if isinstance(name, str) and name != doc.stem:
        findings.append(
            Finding(
                rel,
                key_line(text, 'name'),
                'frontmatter.name-matches-filename',
                f'`name` is {name!r} but the filename is {doc.stem!r}; they must match',
            )
        )

    for schema_path in (base_path, overlay_path):
        if schema_path is None:
            continue
        schema = json.loads(schema_path.read_text(encoding='utf-8'))
        validator = Draft202012Validator(schema)
        for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
            field = str(error.path[0]) if error.path else ''
            rule = f'{corpus}.{field}' if field else f'{corpus}.frontmatter'
            findings.append(
                Finding(
                    rel,
                    key_line(text, field) if field else 1,
                    rule,
                    f'{error.message} (per {schema_path.relative_to(root).as_posix()})',
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
    """Walk up from `start` for the repository root, the directory holding docs/__meta__/."""
    for candidate in (start, *start.parents):
        if (candidate / META_DIR).is_dir():
            return candidate
    return None


USAGE_EXAMPLES = """\
\b
examples:
  check_header.py                            check every governed corpus under docs/
  check_header.py docs/code/python-typing.md check named documents
  check_header.py --format json              machine-readable findings
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
    """Check docs/ frontmatter against the JSON Schemas in docs/__meta__/."""
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
        doc_findings, governed = validate(root, doc)
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
            print(f'{path}:1: [corpus.ungoverned] no header schema for this corpus; frontmatter unvalidated')
        print(f'checked {len(docs)} file(s), {len(findings)} finding(s)', file=sys.stderr)

    raise typer.Exit(code=1 if findings else 0)


if __name__ == '__main__':
    app()
