"""The validator's diagnostic wording for the per-key failures Lorecraft reports one key at a time."""


def required_message(field: str) -> str:
    """Return the wording for one missing `required` property."""
    return f'{field!r} is a required property'


def dependency_message(field: str, dependency: str) -> str:
    """Return the wording for one property missing because `field` is written."""
    return f'{dependency!r} is a dependency of {field!r}'


def additional_message(key: str) -> str:
    """Return the wording for one property refused by `additionalProperties`."""
    return f'Additional properties are not allowed ({key!r} was unexpected)'


def unevaluated_message(key: str) -> str:
    """Return the wording for one property refused by `unevaluatedProperties`."""
    return f'Unevaluated properties are not allowed ({key!r} was unexpected)'
