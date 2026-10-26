"""Generate one page per rule, removed rules and engine conditions included.

The pages go into `docs/rulebook/`, unless `--outdir` names another directory.

Each page is rendered by the function `lorecraft rule` prints it with, from the docstring of the rule's class, so a
rule is documented once, beside its declaration. A page is overwritten, and a stale page, one named like a rule's page
(`<CODE>-<name>.md`) that no rule has any more, is deleted. Any other file in the directory is left alone.
"""

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from lorecraft import rules
from lorecraft.cli.rulebook import page_name, render_page
from lorecraft.rules.registry import Registry

_DEFAULT_OUTDIR: Final[Path] = Path('docs/rulebook')

# The file name `page_name` gives a rule's page, such as `LC304-empty-section.md`.
_PAGE_FILENAME: Final[re.Pattern[str]] = re.compile(r'[A-Z]+[0-9]+-[a-z0-9-]+\.md')


@dataclass(frozen=True, slots=True)
class RulebookWrite:
    """What a rulebook write did to the directory, each list in the order the paths were handled.

    Attributes:
        written: The pages written, one per rule.
        removed: The pages deleted because no rule has that code or name any more.
    """

    written: tuple[Path, ...]
    removed: tuple[Path, ...]


def write_rulebook(outdir: Path) -> RulebookWrite:
    """Write the page of every rule in the registry, and delete the stale ones.

    Args:
        outdir: The directory the pages go into; created if absent. Only a file named like a rule's page,
            `<CODE>-<name>.md`, that no rule has any more is deleted, and any other file is left alone.

    Returns:
        The pages written and the pages removed.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    registry = Registry.load(rules)

    pages = {outdir / f'{page_name(declaration)}.md': render_page(declaration) for declaration in registry.rules}
    for path, page in pages.items():
        path.write_text(page, encoding='utf-8')
    removed = tuple(
        stale_path
        for stale_path in sorted(outdir.glob('*.md'))
        if _PAGE_FILENAME.fullmatch(stale_path.name) and stale_path not in pages
    )
    for stale_path in removed:
        stale_path.unlink()
    return RulebookWrite(written=tuple(pages), removed=removed)


def main() -> None:
    """Write the rulebook into the output directory, and print each page written and removed.

    The output directory is the `--outdir` option, and `docs/rulebook` when it is absent.
    """
    parser = argparse.ArgumentParser(description='Generate one page per rule of the rulebook.')
    parser.add_argument(
        '--outdir',
        type=Path,
        default=_DEFAULT_OUTDIR,
        help=(
            'the directory the pages are written into; a page no rule has any more, named <CODE>-<name>.md, is '
            'deleted and any other file is left alone (default: %(default)s)'
        ),
    )
    outdir: Path = parser.parse_args().outdir

    print('Generating the rulebook...')
    result = write_rulebook(outdir)
    for path in result.written:
        print(f'  {path}')
    for path in result.removed:
        print(f'  {path} (removed)')


if __name__ == '__main__':
    main()
