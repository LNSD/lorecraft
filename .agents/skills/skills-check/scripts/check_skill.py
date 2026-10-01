#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml>=6.0,<7",
#   "typer>=0.12,<1",
# ]
# ///
"""Check where skills live, and find the skills that link a repository file in through `metadata`.

Every rule of the Agent Skills specification (https://agentskills.io/specification) is
checked by `lorecraft check skills`: the frontmatter, the SKILL.md line budget and every
link in a skill's Markdown files. This script checks nothing in a skill's files. It
reports a skill directory outside the two places a skill may live, and one without a
SKILL.md, and `--linking` names the skills that depend on a repository file. Judgment
calls stay with the skill - whether a description says when to use the skill, whether
content belongs in SKILL.md or a reference file, whether a reference chain runs too deep.

This is a vendored standalone copy. Its two checks do not move to the lorecraft library:
`lorecraft check skills` finds skills through the agents' skills directories, where
neither applies, so both go with the script.

A skill lives in one of two places, and a directory anywhere else is reported as
`skill.location`:

    .agents/skills/<name>/  workspace skill: used by agents working in this repository.
    skills/<name>/          project skill: installed into other repositories. Project
                            skills live in skills/; a symlink to one from .agents/skills/
                            is checked once, as a project skill.
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

WORKSPACE_DIR = Path('.agents/skills')
PROJECT_DIR = Path('skills')

# The `metadata` subkeys that link repository files into a project skill, named after the
# skill directory the file is linked from. See §4 of this skill's SKILL.md.
LINKED_DIRS = {'references', 'assets', 'scripts'}


@dataclass(frozen=True)
class Finding:
    """One rule a skill breaks, at a line of one of its files."""

    path: str
    line: int
    rule: str
    message: str

    def as_text(self) -> str:
        """The finding as one `path:line: [rule] message` line."""
        return f'{self.path}:{self.line}: [{self.rule}] {self.message}'

    def as_dict(self) -> dict[str, str | int]:
        """The finding as a JSON-ready mapping."""
        return {'file': self.path, 'line': self.line, 'rule': self.rule, 'message': self.message}


def split_frontmatter(text: str) -> str | None:
    """Return the YAML between the frontmatter delimiters, or None when there is none."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        return None
    for offset, line in enumerate(lines[1:], start=1):
        if line.strip() == '---':
            return '\n'.join(lines[1:offset])
    return None


def metadata_links(skill_dir: Path) -> set[str]:
    """The repository paths a skill links in through `metadata`, as written there."""
    skill_md = skill_dir / 'SKILL.md'
    if not skill_md.is_file():
        return set()
    block = split_frontmatter(skill_md.read_text(encoding='utf-8'))
    if block is None:
        return set()
    try:
        frontmatter = yaml.safe_load(block)
    except yaml.YAMLError:
        return set()
    if not isinstance(frontmatter, dict) or not isinstance(frontmatter.get('metadata'), dict):
        return set()
    metadata = frontmatter['metadata']
    return {path for subkey in LINKED_DIRS for path in str(metadata.get(subkey, '')).split()}


def is_in_skills_dir(root: Path, skill_dir: Path) -> bool:
    """Whether the skill sits directly in .agents/skills/ or skills/, the two places a skill may live."""
    return skill_dir.parent in (root / WORKSPACE_DIR, root / PROJECT_DIR)


def validate(root: Path, skill_dir: Path) -> list[Finding]:
    """Check that one skill directory is where a skill may live, and that it holds a SKILL.md."""
    skill_md = skill_dir / 'SKILL.md'
    rel = skill_md.relative_to(root).as_posix()
    if not is_in_skills_dir(root, skill_dir):
        message = f'skills live directly under {WORKSPACE_DIR}/ or {PROJECT_DIR}/'
        return [Finding(skill_dir.relative_to(root).as_posix(), 1, 'skill.location', message)]
    if not skill_md.is_file():
        return [Finding(rel, 1, 'skill.missing', 'a skill directory must contain SKILL.md')]
    return []


def collect(root: Path, paths: list[Path]) -> list[Path]:
    """Resolve the arguments to skill directories; a SKILL.md or any file inside a skill names its skill.

    A skill directory is resolved through symlinks: a project skill linked into the workspace is one skill,
    checked once and as a project skill.
    """
    if not paths:
        return sorted(
            {
                skill_md.parent.resolve()
                for skills_dir in (root / WORKSPACE_DIR, root / PROJECT_DIR)
                for skill_md in skills_dir.glob('*/SKILL.md')
            }
        )

    skill_dirs: set[Path] = set()
    for path in paths:
        path = path.resolve()
        for candidate in (path, *path.parents):
            if candidate.parent in (root / WORKSPACE_DIR, root / PROJECT_DIR):
                skill_dirs.add(candidate)
                break
        else:
            skill_dirs.add(path if path.is_dir() else path.parent)
    return sorted(skill_dirs)


def repo_relative(root: Path, path: Path) -> str:
    """A path as it would be written in `metadata`: relative to the repository root, forward slashes."""
    candidate = path if path.is_absolute() else Path.cwd() / path
    resolved = candidate.resolve()
    if resolved.is_relative_to(root):
        return resolved.relative_to(root).as_posix()
    return path.as_posix()


def find_root(start: Path) -> Path | None:
    """Walk up from `start` for the repository root, the directory holding .agents/skills/."""
    for candidate in (start, *start.parents):
        if (candidate / WORKSPACE_DIR).is_dir():
            return candidate
    return None


USAGE_EXAMPLES = """\
\b
examples:
  check_skill.py                              check every skill in .agents/skills/ and skills/
  check_skill.py .agents/skills/code-rules    check named skills
  check_skill.py .agents/skills/code-rules/SKILL.md
                                              a file inside a skill names its skill
  check_skill.py --format json                machine-readable findings
  check_skill.py --linking docs/code/logging.md
                                              only the skills whose metadata links that file,
                                              printed one per line before any findings
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
        typer.Argument(help='skill directories or files inside them; defaults to every skill'),
    ] = None,
    root: Annotated[
        Path | None,
        typer.Option(help='repository root (default: found by walking up from the current directory)'),
    ] = None,
    output_format: Annotated[
        OutputFormat,
        typer.Option('--format', help='output format'),
    ] = OutputFormat.text,
    linking: Annotated[
        list[Path] | None,
        typer.Option('--linking', help='check only the skills whose `metadata` links these repository files'),
    ] = None,
) -> None:
    """Check where skills live; `lorecraft check skills` holds them to the Agent Skills specification."""
    if root is not None:
        root = root.resolve()
        if not (root / WORKSPACE_DIR).is_dir():
            print(f'--root {root} has no {WORKSPACE_DIR}/; give the repository root', file=sys.stderr)
            raise typer.Exit(code=2)
    else:
        found = find_root(Path.cwd())
        if found is None:
            print(
                f'no {WORKSPACE_DIR}/ in the current directory or any parent; '
                'run from inside the repository or pass --root',
                file=sys.stderr,
            )
            raise typer.Exit(code=2)
        root = found

    for path in paths or []:
        if not path.exists():
            print(f'no such file: {path}', file=sys.stderr)
            raise typer.Exit(code=2)
        if not path.resolve().is_relative_to(root):
            print(f'{path} is outside the repository at {root}', file=sys.stderr)
            raise typer.Exit(code=2)

    skill_dirs = collect(root, paths or [])

    linked: list[tuple[Path, str]] = []
    if linking:
        wanted = {repo_relative(root, path) for path in linking}
        linked = [
            (skill_dir, repo_path)
            for skill_dir in skill_dirs
            for repo_path in sorted(metadata_links(skill_dir) & wanted)
        ]
        skill_dirs = sorted({skill_dir for skill_dir, _ in linked})

    findings: list[Finding] = []
    for skill_dir in skill_dirs:
        findings.extend(validate(root, skill_dir))

    if output_format is OutputFormat.json:
        report = {
            'checked': len(skill_dirs),
            'linked': [{'skill': d.relative_to(root).as_posix(), 'file': f} for d, f in linked],
            'findings': [f.as_dict() for f in findings],
        }
        print(json.dumps(report, indent=2))
    else:
        for skill_dir, repo_path in linked:
            print(f'{skill_dir.relative_to(root).as_posix()} links {repo_path}')
        for finding in findings:
            print(finding.as_text())
        print(f'checked {len(skill_dirs)} skill(s), {len(findings)} finding(s)', file=sys.stderr)

    raise typer.Exit(code=1 if findings else 0)


if __name__ == '__main__':
    app()
