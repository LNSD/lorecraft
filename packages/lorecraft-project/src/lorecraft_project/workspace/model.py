"""The workspace model: an immutable snapshot of which corpora, specs and documents a repository declares.

The loader builds one model per run from ``docs/__meta__/`` and the corpus directories; every query here is
pure. The model holds structure (corpora, document refs) and configuration (decoded specs), never document
content: text stays behind the document repository and is read on demand through a ``DocumentRef``.

Governance is the one computation the model owns. A document is governed by its corpus spec first, then by
every namespace spec whose namespace matches its filename, broad to narrow. A namespace spec narrows a
base; it never supplies one, so a corpus spec without a header aspect leaves the document ungoverned for the
header aspect whatever the namespace specs carry.
"""

from dataclasses import dataclass

from lorecraft_project.aspect import AspectFilename, AspectNamespace
from lorecraft_project.corpus import CorpusName
from lorecraft_project.document.ref import DocumentRef
from lorecraft_project.schemas.header import HeaderAspect
from lorecraft_project.schemas.name import SchemaName
from lorecraft_vfs import RootRelativePath


@dataclass(frozen=True, slots=True)
class Spec:
    """One specification stem in docs/__meta__ and the aspects decoded from it.

    Not hashable: ``HeaderAspect`` holds a dict, so instances must not be put in a set or used as a key.
    Later aspects slot in as sibling fields: ``structure: StructureAspect | None``,
    ``budget: BudgetAspect | None``.

    Attributes:
        name: The stem, parsed.
        files: Every root-relative file at this stem (prose and JSON), sorted; may be prose only.
        header: The header aspect, or None when ``<stem>.header.json`` does not exist.
    """

    name: SchemaName
    files: tuple[RootRelativePath, ...]
    header: HeaderAspect | None

    @property
    def corpus(self) -> CorpusName:
        """The corpus this stem belongs to."""
        return self.name[0]

    @property
    def namespace(self) -> AspectNamespace | None:
        """The namespace of a ``<corpus>-<namespace>`` stem; None for a corpus stem."""
        if len(self.name) == 1:
            return None
        return self.name[1]

    def governs(self, filename: AspectFilename) -> bool:
        """True for a corpus stem always; for a namespace stem when the namespace matches."""
        if self.namespace is None:
            return True
        return self.namespace.matches(str(filename))


@dataclass(frozen=True, slots=True)
class Governance:
    """The specs that govern one document, broad to narrow.

    Attributes:
        ref: The governed document.
        specs: The corpus spec first, then every matching namespace spec. Never empty.
    """

    ref: DocumentRef
    specs: tuple[Spec, ...]

    def __post_init__(self) -> None:
        """Reject a governance with no specs: the corpus spec is always there.

        Raises:
            ValueError: If ``specs`` is empty.
        """
        if not self.specs:
            raise ValueError(f'document {self.ref.path} must be governed by at least its corpus spec')

    def header_schemas(self) -> tuple[HeaderAspect, ...]:
        """Header aspects to apply in order; ``()`` means ungoverned for the header aspect.

        A corpus spec without a header aspect leaves the document ungoverned even when a matching namespace
        spec carries one: a namespace narrows a base, it cannot supply one.
        """
        if self.specs[0].header is None:
            return ()
        aspects: list[HeaderAspect] = []
        for spec in self.specs:
            if spec.header is not None:
                aspects.append(spec.header)
        return tuple(aspects)


def namespace_order_key(namespace: AspectNamespace) -> tuple[int, str]:
    """The broad-to-narrow order of a corpus's namespace specs: segment count first, then value.

    Every namespace matching one filename is a prefix of that filename, so segment count is broadness and two
    matches never tie; the value tiebreak only orders non-matching siblings.
    """
    value = str(namespace)
    return (value.count('-'), value)


@dataclass(frozen=True, slots=True)
class Corpus:
    """One corpus: its spec, the namespace specs narrowing it, and its document refs.

    Attributes:
        name: Directory name under docs/.
        spec: The corpus stem; always present (discovery is spec-first), possibly prose only.
        namespace_specs: Narrowing stems, sorted broad to narrow by (segment count, value).
        documents: Refs of the Markdown files directly inside docs/<name>/, sorted by filename.
    """

    name: CorpusName
    spec: Spec
    namespace_specs: tuple[Spec, ...]
    documents: tuple[DocumentRef, ...]

    def __post_init__(self) -> None:
        """Reject a corpus whose parts do not all belong to it.

        Raises:
            ValueError: If ``spec.name != (name,)``, a namespace spec has no namespace or another corpus,
                ``namespace_specs`` is not broad-to-narrow, or a ref names another corpus.
        """
        if self.spec.name != (self.name,):
            raise ValueError(f'corpus {self.name} must carry its own corpus spec, got stem {self.spec.name}')
        order_keys: list[tuple[int, str]] = []
        for namespace_spec in self.namespace_specs:
            if namespace_spec.namespace is None:
                raise ValueError(f'corpus {self.name} lists corpus stem {namespace_spec.name} as a namespace spec')
            if namespace_spec.corpus != self.name:
                raise ValueError(f'corpus {self.name} lists namespace spec {namespace_spec.name} of another corpus')
            order_keys.append(namespace_order_key(namespace_spec.namespace))
        if order_keys != sorted(order_keys):
            raise ValueError(f'corpus {self.name} namespace specs are not broad to narrow: {order_keys}')
        for ref in self.documents:
            if ref.corpus != self.name:
                raise ValueError(f'corpus {self.name} lists document {ref.path} of another corpus')

    def governance(self, ref: DocumentRef) -> Governance:
        """Corpus spec, then every namespace spec that matches, in stored order. Pure.

        Raises:
            ValueError: If ``ref.corpus != name``.
        """
        if ref.corpus != self.name:
            raise ValueError(f'document {ref.path} is not in corpus {self.name}')
        specs: list[Spec] = [self.spec]
        for namespace_spec in self.namespace_specs:
            if namespace_spec.governs(ref.filename):
                specs.append(namespace_spec)
        return Governance(ref, tuple(specs))


@dataclass(frozen=True, slots=True)
class WorkspaceModel:
    """Immutable snapshot of structure and config; holds no root path and no document content.

    Attributes:
        corpora: Every corpus, sorted by name.
    """

    corpora: tuple[Corpus, ...]

    def corpus(self, name: CorpusName) -> Corpus | None:
        """The corpus with this name, or None when the model has none."""
        for corpus in self.corpora:
            if corpus.name == name:
                return corpus
        return None

    def documents(self) -> tuple[DocumentRef, ...]:
        """Every ref, corpus order then filename order."""
        refs: list[DocumentRef] = []
        for corpus in self.corpora:
            refs.extend(corpus.documents)
        return tuple(refs)

    def locate(self, path: RootRelativePath) -> DocumentRef | None:
        """The ref whose ``path`` equals this root-relative path, or None."""
        for ref in self.documents():
            if ref.path == path:
                return ref
        return None

    def governance(self, ref: DocumentRef) -> Governance:
        """The specs governing a document this model lists.

        Raises:
            KeyError: If ``ref.corpus`` is not a corpus of this model (refs from the model never trigger it).
        """
        corpus = self.corpus(ref.corpus)
        if corpus is None:
            raise KeyError(str(ref.corpus))
        return corpus.governance(ref)
