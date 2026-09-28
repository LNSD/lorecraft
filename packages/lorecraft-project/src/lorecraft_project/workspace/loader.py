"""Build the workspace model from the specification directory, the corpus directories and the skills directories.

Discovery is spec-first: a directory under ``docs/`` is a corpus only when ``docs/__meta__/`` holds a file at
its stem. The loader lists the specification directory, parses each filename once with ``parse_spec_file``,
sorts the parsed files into corpus stems, namespace stems and type selectors, keeps the corpora whose
``docs/<corpus>/`` is a regular directory, lists the Markdown files directly inside each, and builds a
``HeaderAspect`` from every header schema, which proves it well-formed, before any document is read. It then
discovers the skills through ``load_skills``, without reading any SKILL.md. An entry that does not fit the
layout is left out of the model; nothing it leaves out fails the run.

Nothing here logs and nothing here catches broadly: a repository or schema error names its path already, so
it propagates unchanged to the command that loads the model, which reports it.
"""

from dataclasses import dataclass, field

from lorecraft_project.aspect import AspectFilename, AspectFilenameError, AspectName, AspectNamespace
from lorecraft_project.corpus import CorpusName
from lorecraft_project.document.ref import DocumentRef
from lorecraft_project.document.repo import Repository as DocumentRepository
from lorecraft_project.layout import SPECS_DIR
from lorecraft_project.schemas.header import HeaderAspect
from lorecraft_project.schemas.name import SchemaName
from lorecraft_project.schemas.repo import Repository as SchemaRepository
from lorecraft_project.schemas.spec_file import (
    SpecAspect,
    SpecFile,
    SpecFilenameError,
    TypeSelectorFile,
    parse_spec_file,
)
from lorecraft_project.skill.repo import Repository as SkillRepository
from lorecraft_vfs import EntryKind, FileSystem, RootRelativePath

from .model import Corpus, Spec, TypeSelector, WorkspaceModel, namespace_order_key
from .skill_loader import load_skills


@dataclass(slots=True)
class _CorpusFiles:
    """The specification files naming one corpus, gathered before ``docs/<corpus>/`` is checked.

    Attributes:
        spec: Files at the ``<corpus>`` stem; empty when the corpus has no spec of its own.
        namespaces: Files at each ``<corpus>-<namespace>`` stem, keyed by namespace.
        selectors: Files at each ``<corpus>.<type>`` stem, keyed by document type.
    """

    spec: list[SpecFile] = field(default_factory=list)
    namespaces: dict[AspectNamespace, list[SpecFile]] = field(default_factory=dict)
    selectors: dict[AspectName, list[TypeSelectorFile]] = field(default_factory=dict)


def load_workspace(schemas: SchemaRepository, documents: DocumentRepository, skills: SkillRepository) -> WorkspaceModel:
    """Build the snapshot: parse the spec filenames, keep corpus stems whose docs/<corpus>/ is a directory, list
    the Markdown files directly inside each, build a header aspect from every header schema; then ``load_skills`` over
    the canonical and agent directories, without reading any SKILL.md.

    Raises:
        ListSpecsError: If the specification directory cannot be listed.
        ListCorpusDirectoriesError: If docs/ cannot be listed.
        ListDocumentsError: If a corpus directory cannot be listed.
        GetHeaderSchemaError: If any header schema cannot be read or decoded.
        InvalidHeaderSchemaError: If any header schema is not a well-formed JSON Schema.
        ListSkillEntriesError: If a skills directory cannot be listed.
        ResolveSkillDirectoryError: If a skills path cannot be resolved.
        ProbeSkillMdError: If a skill directory cannot be listed for its SKILL.md.
    """
    spec_paths = schemas.list_spec_paths()
    directories = documents.list_corpus_directories()

    groups = _group_spec_files(spec_paths)
    directory_kinds: dict[str, EntryKind] = {entry.name: entry.kind for entry in directories}

    corpora: list[Corpus] = []
    for corpus_name in sorted(groups, key=str):
        files = groups[corpus_name]
        if str(corpus_name) == SPECS_DIR.name:
            # `__meta__` is a valid corpus name, so a stray `__meta__.md` would otherwise turn the
            # specification directory into a corpus whose documents are the specifications themselves.
            continue
        if not files.spec:
            # A namespace or a type selector narrows a corpus spec; without one there is nothing to narrow.
            continue
        directory_kind = directory_kinds.get(str(corpus_name))
        if directory_kind is None or directory_kind is EntryKind.SYMLINK:
            # A corpus is a regular directory under docs/; a missing one has no documents to list.
            continue
        refs = _list_document_refs(documents, corpus_name)
        corpora.append(_load_corpus(schemas, corpus_name, files, refs))

    skill_set = load_skills(skills)
    return WorkspaceModel(corpora=tuple(corpora), skills=skill_set)


def load_model(fs: FileSystem) -> WorkspaceModel:
    """Wire one filesystem view into the three repositories and load the workspace model through them.

    The view decides where the model comes from: a ``DiskFileSystem`` reads the disk as it is at each call,
    and a ``VirtualFileSystem`` answers from one snapshot, so the model reflects a single moment.

    Raises:
        ListSpecsError: If the specification directory cannot be listed.
        ListCorpusDirectoriesError: If docs/ cannot be listed.
        ListDocumentsError: If a corpus directory cannot be listed.
        GetHeaderSchemaError: If any header schema cannot be read or decoded.
        InvalidHeaderSchemaError: If any header schema is not a well-formed JSON Schema.
        ListSkillEntriesError: If a skills directory cannot be listed.
        ResolveSkillDirectoryError: If a skills path cannot be resolved.
        ProbeSkillMdError: If a skill directory cannot be listed for its SKILL.md.
    """
    schemas = SchemaRepository(fs, SPECS_DIR)
    documents = DocumentRepository(fs)
    skills = SkillRepository(fs)
    return load_workspace(schemas, documents, skills)


def _group_spec_files(spec_paths: list[RootRelativePath]) -> dict[CorpusName, _CorpusFiles]:
    """Parse every file in the specification directory and file it under the corpus its stem names.

    A file whose name does not parse as a specification filename, such as ``README.md``, is left out.
    """
    groups: dict[CorpusName, _CorpusFiles] = {}
    for path in spec_paths:
        try:
            spec_file = parse_spec_file(path)
        except SpecFilenameError:
            continue

        group = groups.setdefault(spec_file.corpus, _CorpusFiles())
        if isinstance(spec_file, TypeSelectorFile):
            group.selectors.setdefault(spec_file.name.document_type, []).append(spec_file)
        elif len(spec_file.name) == 1:
            group.spec.append(spec_file)
        else:
            group.namespaces.setdefault(spec_file.name[1], []).append(spec_file)
    return groups


def _load_corpus(
    schemas: SchemaRepository, corpus_name: CorpusName, files: _CorpusFiles, refs: list[DocumentRef]
) -> Corpus:
    """Decode the corpus spec and its namespace specs, and record its type selectors.

    Raises:
        GetHeaderSchemaError: If a header schema cannot be read or decoded.
        InvalidHeaderSchemaError: If a header schema is not a well-formed JSON Schema.
    """
    spec = _load_spec(schemas, (corpus_name,), files.spec)

    # Broad to narrow: every namespace matching one filename is a prefix of that filename, so segment count
    # is broadness and two matches never tie; the value tiebreak only orders non-matching siblings.
    namespace_specs: list[Spec] = []
    for namespace in sorted(files.namespaces, key=namespace_order_key):
        namespace_specs.append(_load_spec(schemas, (corpus_name, namespace), files.namespaces[namespace]))

    type_selectors: list[TypeSelector] = []
    for document_type, selector_files in files.selectors.items():
        paths = tuple(sorted((selector_file.path for selector_file in selector_files), key=str))
        type_selectors.append(TypeSelector(corpus=corpus_name, document_type=document_type, files=paths))
    type_selectors.sort(key=lambda selector: str(selector.document_type))

    return Corpus(
        name=corpus_name,
        spec=spec,
        namespace_specs=tuple(namespace_specs),
        type_selectors=tuple(type_selectors),
        documents=tuple(sorted(refs, key=lambda ref: str(ref.filename))),
    )


def _load_spec(schemas: SchemaRepository, name: SchemaName, spec_files: list[SpecFile]) -> Spec:
    """Build one spec from the files at its stem, decoding its header schema into an aspect if it has one.

    Raises:
        GetHeaderSchemaError: If the header schema cannot be read or decoded.
        InvalidHeaderSchemaError: If the header schema is not a well-formed JSON Schema.
    """
    header: HeaderAspect | None = None
    for spec_file in spec_files:
        if spec_file.aspect is SpecAspect.HEADER:
            # Building the aspect is the well-formedness check: HeaderAspect rejects a malformed schema.
            header = HeaderAspect(path=spec_file.path, schema=schemas.get_header_schema(name))
    paths = tuple(sorted((spec_file.path for spec_file in spec_files), key=str))
    return Spec(name=name, files=paths, header=header)


def _list_document_refs(documents: DocumentRepository, corpus_name: CorpusName) -> list[DocumentRef]:
    """The refs of the regular, validly named Markdown files directly inside the corpus; the rest are left out.

    Raises:
        ListDocumentsError: If the corpus directory cannot be listed.
    """
    refs: list[DocumentRef] = []
    for document_file in documents.list_documents(corpus_name):
        if document_file.kind is EntryKind.SYMLINK:
            continue
        try:
            filename = AspectFilename.parse(document_file.stem)
        except AspectFilenameError:
            continue
        refs.append(DocumentRef(corpus=corpus_name, filename=filename))
    return refs
