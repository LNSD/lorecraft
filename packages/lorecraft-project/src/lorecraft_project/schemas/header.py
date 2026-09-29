"""The header aspect: a header schema file's decoded JSON, and the aspect that proves it well-formed.

The repository reads and decodes a ``<stem>.header.json`` file into a ``HeaderSchema``, which proves nothing
about it. Building a ``HeaderAspect`` from it is the check: construction runs the Draft 2020-12 meta-schema, so
every ``HeaderAspect`` that exists holds a well-formed schema, however it was built.

Nothing here logs: the command that loads the model catches every ``Error`` that escapes it and reports it,
so a handler below re-raises without logging.
"""

from dataclasses import dataclass
from typing import NewType

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from lorecraft_core.error import Error
from lorecraft_vfs import RootRelativePath

# The decoded JSON object of a header schema file, not yet known to be a well-formed schema. A NewType only
# keeps it apart from structure JSON; `HeaderAspect` is the type whose construction proves it well-formed.
# Values are `object` because a JSON Schema is recursive and JSON decodes each value to its own Python type.
HeaderSchema = NewType('HeaderSchema', dict[str, object])


class InvalidHeaderSchemaError(Error):
    """A header schema is not a well-formed Draft 2020-12 JSON Schema.

    Attributes:
        path: Root-relative path of the rejected schema file.
    """

    path: RootRelativePath

    def __init__(self, path: RootRelativePath, detail: str) -> None:
        self.path = path
        super().__init__(f'invalid schema {path}: {detail}')


@dataclass(frozen=True, slots=True)
class HeaderAspect:
    """One header schema, well-formed under the Draft 2020-12 meta-schema.

    Construction checks the schema, so an instance is proof of it: no code holding a ``HeaderAspect`` checks
    the schema again.

    Frozen for equality only: ``schema`` is a dict, so instances are not hashable and must not be put in a
    set or used as a key.

    Attributes:
        path: Root-relative path of the JSON file, quoted verbatim as the finding label.
        schema: The decoded schema.
    """

    path: RootRelativePath
    schema: HeaderSchema

    def __post_init__(self) -> None:
        """Reject a schema the Draft 2020-12 meta-schema does not accept.

        Raises:
            InvalidHeaderSchemaError: If ``Draft202012Validator.check_schema`` rejects ``schema``.
        """
        try:
            Draft202012Validator.check_schema(self.schema)
        except SchemaError as exc:
            raise InvalidHeaderSchemaError(self.path, exc.message) from exc
