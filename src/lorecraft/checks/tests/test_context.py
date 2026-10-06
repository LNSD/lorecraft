"""The database-backed contexts, held statically to the protocols of `lorecraft.project` they implement.

The contexts are never declared as subclasses of their protocols, so nothing but the type checker proves that each
class has every member with a compatible type. Each helper below returns a class where its protocol is expected,
which `ty check src` refuses if the class drifts from the protocol; the integration tier holds each method's value.
"""

from lorecraft.checks.context import DatabaseDocumentContext, DatabaseSkillContext
from lorecraft.project.context import DocumentContext, SkillContext


def _as_document_context(context: DatabaseDocumentContext) -> DocumentContext:
    """The document context, as the protocol it implements.

    Args:
        context: The database-backed context of one document.
    """
    return context


def _as_skill_context(context: DatabaseSkillContext) -> SkillContext:
    """The skill context, as the protocol it implements.

    Args:
        context: The database-backed context of one skill.
    """
    return context
