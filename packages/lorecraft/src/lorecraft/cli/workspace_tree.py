"""Draw the workspace model: the text `lorecraft inspect` prints, and the JSON it prints with `--json`.

Pure: the model arrives as a value, so nothing here reads the disk. The text form is a tree with one section
per part of the model — today the corpora — and the JSON form carries the same content as nested objects.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from lorecraft_project.layout import DOCS_DIR
from lorecraft_project.schemas import schema_name_stem
from lorecraft_project.workspace import Corpus, Spec, TypeSelector, WorkspaceModel
from lorecraft_vfs import RootRelativePath

# The box-drawing prefixes `tree` uses: one for an entry with siblings after it, one for the last entry, and
# the matching indent each leaves for the entries nested under it.
_BRANCH: str = '├── '
_LAST_BRANCH: str = '└── '
_INDENT: str = '│   '
_LAST_INDENT: str = '    '


@dataclass(frozen=True, slots=True)
class _Line:
    """One line of the drawn tree and the lines nested under it.

    Attributes:
        label: The text drawn after the branch.
        children: The lines drawn under this one, in order.
    """

    label: str
    children: tuple['_Line', ...] = ()


def render_text(root: Path, model: WorkspaceModel) -> str:
    """Draw the model as a tree headed by the root, one section per part of the model.

    A document is followed by the stems of the specs that govern it, broad to narrow.

    Returns:
        The lines, newline-separated, without a trailing newline.
    """
    sections = (_corpora_section(model.corpora),)
    lines = [str(root)]
    _draw(sections, '', lines)
    return '\n'.join(lines)


def render_json(root: Path, model: WorkspaceModel) -> str:
    """Encode the model as indented JSON, the root beside one key per section: ``{"root", "corpora"}``."""
    corpora: list[dict[str, object]] = []
    for corpus in model.corpora:
        corpora.append(_json_corpus(corpus))
    document = {
        'root': str(root),
        'corpora': corpora,
    }
    return json.dumps(document, indent=2)


def _draw(nodes: tuple[_Line, ...], prefix: str, lines: list[str]) -> None:
    """Append one line per node, and recurse into each node's children with the indent it leaves."""
    for index, node in enumerate(nodes):
        is_last = index == len(nodes) - 1
        branch = _LAST_BRANCH if is_last else _BRANCH
        lines.append(prefix + branch + node.label)
        indent = _LAST_INDENT if is_last else _INDENT
        _draw(node.children, prefix + indent, lines)


def _corpora_section(corpora: tuple[Corpus, ...]) -> _Line:
    """``corpora (N)``, then per corpus its specs, its type selectors when it has any, and its documents."""
    corpus_lines: list[_Line] = []
    for corpus in corpora:
        corpus_lines.append(_corpus_line(corpus))
    return _Line(f'corpora ({len(corpora)})', tuple(corpus_lines))


def _corpus_line(corpus: Corpus) -> _Line:
    """One corpus: the directory it reads, its specs, its type selectors and its governed documents."""
    spec_lines: list[_Line] = []
    for spec in (corpus.spec, *corpus.namespace_specs):
        spec_lines.append(_Line(f'{schema_name_stem(spec.name)}: {_file_names(spec.files)}'))
    parts = [_Line(f'specs ({len(spec_lines)})', tuple(spec_lines))]

    if corpus.type_selectors:
        selector_lines: list[_Line] = []
        for selector in corpus.type_selectors:
            selector_lines.append(_Line(f'{selector.document_type}: {_file_names(selector.files)}'))
        parts.append(_Line(f'type selectors ({len(selector_lines)})', tuple(selector_lines)))

    document_lines: list[_Line] = []
    for ref in corpus.documents:
        stems = _governing_stems(corpus.governance(ref).specs)
        document_lines.append(_Line(f'{ref.path.name} [{", ".join(stems)}]'))
    parts.append(_Line(f'documents ({len(document_lines)})', tuple(document_lines)))

    return _Line(f'{corpus.name} ({DOCS_DIR / str(corpus.name)})', tuple(parts))


def _json_corpus(corpus: Corpus) -> dict[str, object]:
    """One corpus as a JSON object: its specs, its type selectors and its documents with their governance."""
    specs: list[dict[str, object]] = []
    for spec in (corpus.spec, *corpus.namespace_specs):
        specs.append({'stem': schema_name_stem(spec.name), 'files': _paths(spec.files)})
    selectors: list[dict[str, object]] = []
    for selector in corpus.type_selectors:
        selectors.append(_json_type_selector(selector))
    documents: list[dict[str, object]] = []
    for ref in corpus.documents:
        documents.append(
            {'path': str(ref.path), 'governed_by': _governing_stems(corpus.governance(ref).specs)},
        )
    return {
        'name': str(corpus.name),
        'directory': str(DOCS_DIR / str(corpus.name)),
        'specs': specs,
        'type_selectors': selectors,
        'documents': documents,
    }


def _json_type_selector(selector: TypeSelector) -> dict[str, object]:
    """One type selector as a JSON object."""
    return {'type': str(selector.document_type), 'files': _paths(selector.files)}


def _governing_stems(specs: tuple[Spec, ...]) -> list[str]:
    """The stems of the governing specs, broad to narrow, as the model orders them."""
    stems: list[str] = []
    for spec in specs:
        stems.append(schema_name_stem(spec.name))
    return stems


def _file_names(files: tuple[RootRelativePath, ...]) -> str:
    """The file names, comma-separated: every spec file sits in the one specification directory."""
    names: list[str] = []
    for file in files:
        names.append(file.name)
    return ', '.join(names)


def _paths(files: tuple[RootRelativePath, ...]) -> list[str]:
    """The root-relative paths as strings."""
    paths: list[str] = []
    for file in files:
        paths.append(str(file))
    return paths
