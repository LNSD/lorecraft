"""The typed argument of `lorecraft rule [RULE]`, confirmed against the rule index."""

from dataclasses import dataclass
from string import ascii_lowercase, ascii_uppercase, digits
from typing import TYPE_CHECKING, Self

from lorecraft.core.error import Error
from lorecraft.rules import index

from .rule_arguments import IndexRuleNotInRegistryError, RuleIndex

if TYPE_CHECKING:
    from lorecraft.rules.declaration import RuleDeclaration
    from lorecraft.rules.registry import Registry


class MalformedRuleKeyError(Error):
    """A key has the shape of neither a rule's code nor name, and no rule declares it as an alias code.

    Attributes:
        text: The key as typed.
    """

    text: str

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__(
            f'{text!r} is no rule code, name or alias code: write a code such as LC101 or a name such as empty-section'
        )


class UnknownRuleKeyError(Error):
    """A well-formed key names no rule, removed rule or engine condition.

    Attributes:
        text: The key as typed.
    """

    text: str

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__(f'no rule has the code, name or alias code {text!r}')


@dataclass(frozen=True, slots=True)
class RuleKey:
    """The argument of `rule [RULE]`: a rule's code, its name or an alias code, which the index has.

    Attributes:
        text: The key as typed.
    """

    text: str

    @classmethod
    def parse(cls, raw: str, rule_index: RuleIndex = index) -> Self:
        """Parse the argument of `rule [RULE]`, confirmed against the rule index.

        An alias code has no shape of its own: it is one exactly when the index finds a rule for it.

        Args:
            raw: The argument as typed.
            rule_index: The rule index the key is confirmed against.

        Raises:
            MalformedRuleKeyError: If it has the shape of neither a code nor a name, and no rule declares it as an
                alias code.
            UnknownRuleKeyError: If it is shaped as a code or a name, and no rule has it.
        """
        if rule_index.find(raw) is not None:
            return cls(raw)
        if _has_code_shape(raw) or _has_name_shape(raw):
            raise UnknownRuleKeyError(raw)
        raise MalformedRuleKeyError(raw)

    def to_declaration(self, registry: Registry) -> RuleDeclaration:
        """The rule, removed rule or engine condition the key names.

        Args:
            registry: Every rule, which holds the declaration.

        Raises:
            IndexRuleNotInRegistryError: If the registry has no declaration for the key, which the index held.
        """
        declaration = registry.find(self.text)
        if declaration is None:
            raise IndexRuleNotInRegistryError(self.text)
        return declaration

    def __str__(self) -> str:
        """The key as typed."""
        return self.text


def _has_code_shape(text: str) -> bool:
    """Whether text has an uppercase prefix followed by exactly three digits.

    Args:
        text: The text to classify.
    """
    split = len(text) - index.CODE_DIGITS
    return (
        split > 0
        and all(character in ascii_uppercase for character in text[:split])
        and all(character in digits for character in text[split:])
        and int(text[split:]) > 0
    )


def _has_name_shape(text: str) -> bool:
    """Whether text has the shape of a rule's name: kebab-case, with no edge or doubled hyphen.

    Args:
        text: The text to classify.
    """
    characters = ascii_lowercase + digits + '-'
    if not text or any(character not in characters for character in text):
        return False
    return not text.startswith('-') and not text.endswith('-') and '--' not in text
