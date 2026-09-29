"""The workspace model and the loader that builds it through a filesystem view."""

from .loader import load_model, load_workspace
from .model import Corpus, Governance, Spec, WorkspaceModel

__all__ = [
    'WorkspaceModel',
    'Corpus',
    'Spec',
    'Governance',
    'load_workspace',
    'load_model',
]
