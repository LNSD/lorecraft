"""The workspace model and the loader that builds it through a filesystem view."""

from .loader import load_model, load_workspace
from .model import Corpus, CorpusSpec, Governance, NamespaceSpec, Spec, WorkspaceModel

__all__ = [
    'WorkspaceModel',
    'Corpus',
    'Spec',
    'CorpusSpec',
    'NamespaceSpec',
    'Governance',
    'load_workspace',
    'load_model',
]
