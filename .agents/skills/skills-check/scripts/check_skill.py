#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml>=6.0,<7",
#   "typer>=0.12,<1",
# ]
# ///
"""Check the body of skills against the Agent Skills specification (https://agentskills.io/specification).

Covers what `lorecraft check skills` does not yet: the SKILL.md length budget, the files a
project skill links in through `metadata`, and whether every relative link resolves. The
frontmatter - its fields, their limits and the name matching its directory - is checked
by `lorecraft check skills`, and no longer here. Judgment calls stay with the skill -
whether a description says when to use the skill, whether content belongs in SKILL.md or
a reference file, whether a reference chain runs too deep.

This is a vendored standalone copy; the checks it implements are destined for the
lorecraft library, which will run them from one checker instead of a script per skill.

A skill's location decides which rules apply:

    .agents/skills/<name>/  workspace skill: used by agents working in this repository.
                            The specification, plus links into the repository.
    skills/<name>/          project skill: installed into other repositories. The
                            specification only, and no link may leave the skill, except
                            through the `metadata` convention described in SKILL.md.
                            Project skills live in skills/; a symlink to one from
                            .agents/skills/ is checked once, as a project skill.
"""

from __future__ import annotations

import json
import re
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

SKILL_MD_MAX_LINES = 500

LINK_PATTERN = re.compile(r'\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)')
FENCE_PATTERN = re.compile(r'^\s*(```|~~~)')


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


class SkillKind(str, Enum):
    """Where a skill lives, which decides the rules it is held to."""

    workspace = 'workspace'
    project = 'project'


def split_frontmatter(text: str) -> str | None:
    """Return the YAML between the frontmatter delimiters, or None when there is none."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        return None
    for offset, line in enumerate(lines[1:], start=1):
        if line.strip() == '---':
            return '\n'.join(lines[1:offset])
    return None


def load_frontmatter(text: str) -> dict:
    """The frontmatter mapping of a SKILL.md, or an empty one when it has none that can be read.

    An unusable frontmatter is `lorecraft check skills`'s finding, so it is not reported here:
    the body is checked as the body of a skill that links nothing in.
    """
    block = split_frontmatter(text)
    if block is None:
        return {}
    try:
        frontmatter = yaml.safe_load(block)
    except yaml.YAMLError:
        return {}
    if not isinstance(frontmatter, dict):
        return {}
    return frontmatter


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


def key_line(text: str, key: str) -> int:
    """Line number of a top-level frontmatter key, or 1 when it is absent."""
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip() == '---' and number > 1:
            break
        if line.startswith(f'{key}:'):
            return number
    return 1


def skill_kind(root: Path, skill_dir: Path) -> SkillKind | None:
    if skill_dir.parent == root / WORKSPACE_DIR:
        return SkillKind.workspace
    if skill_dir.parent == root / PROJECT_DIR:
        return SkillKind.project
    return None


def linked_files(root: Path, rel: str, text: str, frontmatter: dict) -> tuple[dict[Path, Path], list[Finding]]:
    """Map each repository file a project skill links in through `metadata` to its path inside the skill.

    `references: docs/code/logging.md` makes `references/logging.md` resolve to
    `docs/code/logging.md`, which is how §4 of this skill's SKILL.md says the links resolve.
    `lorecraft check skills` reports two listed files that share a name under one subkey.
    """
    metadata = frontmatter.get('metadata')
    if not isinstance(metadata, dict):
        return {}, []

    links: dict[Path, Path] = {}
    findings: list[Finding] = []
    for subkey in LINKED_DIRS:
        value = metadata.get(subkey)
        if not isinstance(value, str):
            continue
        for repo_path in value.split():
            file_name = Path(repo_path).name
            if not (root / repo_path).is_file():
                findings.append(
                    Finding(
                        rel,
                        key_line(text, 'metadata'),
                        'metadata.missing-file',
                        f'`metadata.{subkey}` lists `{repo_path}`, which does not exist',
                    )
                )
            links[Path(subkey) / file_name] = root / repo_path
    return links, findings


def check_body(root: Path, skill_dir: Path, path: Path, kind: SkillKind, links: dict[Path, Path]) -> list[Finding]:
    """Check the relative links in one Markdown file of a skill."""
    rel = path.relative_to(root).as_posix()
    findings: list[Finding] = []
    in_fence = False

    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        if FENCE_PATTERN.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        for target in LINK_PATTERN.findall(line):
            if re.match(r'^[a-z][a-z0-9+.-]*:', target):
                continue
            target_path, _, _ = target.partition('#')
            if not target_path:
                # `lorecraft check skills` reports this as `skill.link-fragment`, for `SKILL.md` only.
                continue
            if target_path.startswith('/'):
                # `lorecraft check skills` reports this as `skill.link-absolute`, for `SKILL.md` only.
                continue

            resolved = (path.parent / target_path).resolve()
            inside_skill = resolved.is_relative_to(skill_dir.resolve())

            target_file: Path | None = None
            if inside_skill and resolved.exists():
                target_file = resolved
            elif inside_skill and resolved.relative_to(skill_dir.resolve()) in links:
                target_file = links[resolved.relative_to(skill_dir.resolve())]
            elif kind is SkillKind.workspace and resolved.exists():
                target_file = resolved

            if target_file is None:
                if kind is SkillKind.project and not inside_skill:
                    message = f'`{target}` leaves the skill directory; link the file in through `metadata` instead'
                    findings.append(Finding(rel, number, 'link.escapes', message))
                else:
                    findings.append(Finding(rel, number, 'link.broken', f'`{target}` does not resolve'))
                continue

    return findings


def validate(root: Path, skill_dir: Path) -> list[Finding]:
    skill_md = skill_dir / 'SKILL.md'
    rel = skill_md.relative_to(root).as_posix()
    kind = skill_kind(root, skill_dir)
    if kind is None:
        message = f'skills live directly under {WORKSPACE_DIR}/ or {PROJECT_DIR}/'
        return [Finding(skill_dir.relative_to(root).as_posix(), 1, 'skill.location', message)]
    if not skill_md.is_file():
        return [Finding(rel, 1, 'skill.missing', 'a skill directory must contain SKILL.md')]

    text = skill_md.read_text(encoding='utf-8')
    frontmatter = load_frontmatter(text)
    findings: list[Finding] = []

    line_count = len(text.splitlines())
    if line_count > SKILL_MD_MAX_LINES:
        message = f'SKILL.md is {line_count} lines; keep it under {SKILL_MD_MAX_LINES} and move detail to references/'
        findings.append(Finding(rel, 1, 'body.length', message))

    links: dict[Path, Path] = {}
    if kind is SkillKind.project:
        links, metadata_findings = linked_files(root, rel, text, frontmatter)
        findings.extend(metadata_findings)

    for markdown in sorted(skill_dir.rglob('*.md')):
        findings.extend(check_body(root, skill_dir, markdown, kind, links))

    return findings


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
    """Check the body of skills against the Agent Skills specification; `lorecraft check skills` has the frontmatter."""
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
