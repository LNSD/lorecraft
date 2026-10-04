"""The rules engine's runner over a database opened on an in-memory snapshot.

The runner decodes each document, builds each input an enabled rule reads, and runs the rules of a table built
from a registry. The package's own registry runs the token budget; a registry of sample rules over the same input,
declared in this module, runs through the same runner, with no edit to it.
"""

from dataclasses import dataclass
from typing import ClassVar, Final, Self

import pytest

from lorecraft.checks import Database, DocumentText
from lorecraft.checks.report import CheckedSubject, RuleDiagnostic, UndecodableSubject
from lorecraft.checks.runner import check_subjects
from lorecraft.checks.table import RuleTable
from lorecraft.core.path import RootRelativePath
from lorecraft.project.aspect import AspectFilename
from lorecraft.project.corpus import CorpusName
from lorecraft.project.document import DocumentRef
from lorecraft.project.syntax import LineNumber, count_tokens
from lorecraft.rules.declaration import Level, Release, Rule, RuleCode, RuleGroup, RuleName, Severity
from lorecraft.rules.inputs import InputKind, TokenCountInput, TokenCountRule
from lorecraft.rules.length.too_many_tokens import TooManyTokens
from lorecraft.rules.registry import Registry, package_registry
from lorecraft.vfs import Snapshot

GUIDE: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('guide'))
"""A document of corpus `code`."""

INTRO: Final[DocumentRef] = DocumentRef(CorpusName.parse('code'), AspectFilename.parse('intro'))
"""A second document of corpus `code`."""

GUIDE_TEXT: Final[str] = '# Guide\n\nInstall the toolkit, then run it once over the repository.\n'
"""The text of `GUIDE`."""

CODE_SPEC: Final[RootRelativePath] = RootRelativePath.parse('docs/__meta__/code.structure.json')
"""The corpus structure specification."""

SAMPLE: Final[RuleGroup] = RuleGroup('SMP', 'Sample rules')
"""The group of the sample rules this module declares."""


@dataclass(frozen=True, slots=True, kw_only=True)
class OverHalfBudget(TokenCountRule):
    """A sample rule at `warn`: a document holds more than half the tokens a budget allows.

    Attributes:
        spec: The structure specification that sets the budget.
        token_count: The tokens in the document's whole file.
        budget: The budget, in tokens.
    """

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 1)
    NAME: ClassVar[RuleName] = RuleName('over-half-budget')
    LEVEL: ClassVar[Level] = Level.WARN
    SINCE: ClassVar[Release] = Release('1.0.0')

    spec: RootRelativePath
    token_count: int
    budget: int

    def message(self) -> str:
        """Name the tokens found against the budget."""
        return f'over half the budget ({self.token_count} of {self.budget})'

    @classmethod
    def check(cls, subject: TokenCountInput) -> tuple[Self, ...]:
        """One occurrence for each budget the document holds more than half of.

        Args:
            subject: The document's token count, with the budgets that govern it.
        """
        return tuple(
            cls(
                spec=budget.spec,
                line=LineNumber.from_int(1),
                token_count=subject.token_count.value,
                budget=budget.tokens.value,
            )
            for budget in subject.budgets
            if subject.token_count.value * 2 > budget.tokens.value
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EmptyDocument(TokenCountRule):
    """A sample rule at `allow`: a document holds no token at all."""

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 2)
    NAME: ClassVar[RuleName] = RuleName('empty-document')
    LEVEL: ClassVar[Level] = Level.ALLOW
    SINCE: ClassVar[Release] = Release('1.0.0')

    def message(self) -> str:
        """Name the condition."""
        return 'document is empty'

    @classmethod
    def check(cls, subject: TokenCountInput) -> tuple[Self, ...]:
        """The occurrence at line 1, when the document has no token.

        Args:
            subject: The document's token count, with the budgets that govern it.
        """
        if subject.token_count.value > 0:
            return ()
        return (cls(spec=None, line=LineNumber.from_int(1)),)


@dataclass(frozen=True, slots=True, kw_only=True)
class AnyTokens(TokenCountRule):
    """A sample rule at `deny` that fires once on every document a budget governs, whatever its token count.

    Attributes:
        token_count: The tokens in the document's whole file.
    """

    CODE: ClassVar[RuleCode] = RuleCode(SAMPLE, 3)
    NAME: ClassVar[RuleName] = RuleName('any-tokens')
    LEVEL: ClassVar[Level] = Level.DENY
    SINCE: ClassVar[Release] = Release('1.0.0')

    token_count: int

    def message(self) -> str:
        """Name the tokens counted."""
        return f'document counted ({self.token_count} tokens)'

    @classmethod
    def check(cls, subject: TokenCountInput) -> tuple[Self, ...]:
        """One occurrence at line 1, whatever the count.

        Args:
            subject: The document's token count, with the budgets that govern it.
        """
        return (cls(spec=None, line=LineNumber.from_int(1), token_count=subject.token_count.value),)


class CountingDatabase(Database):
    """A database that records each document whose tokens it is asked to count, then counts them as usual."""

    def __init__(self, snapshot: Snapshot) -> None:
        """Open the database on the snapshot, with nothing counted yet.

        Args:
            snapshot: The revision the database reads.
        """
        super().__init__(snapshot)
        self.counted: list[DocumentRef] = []

    def tokens(self, source: DocumentText) -> int:
        """Record the document, then count its tokens.

        Args:
            source: The decoded document whose tokens are counted, recorded by its ref first.
        """
        self.counted.append(source.ref)
        return super().tokens(source)


def _snapshot(structure_spec: bytes, *, guide: bytes, intro: bytes = b'# Intro\n') -> Snapshot:
    """A snapshot of corpus `code`, holding the documents `GUIDE` and `INTRO`.

    Args:
        structure_spec: Bytes of the corpus structure specification.
        guide: Bytes of `GUIDE`.
        intro: Bytes of `INTRO`.
    """
    return Snapshot.from_tree(
        {
            'docs': {
                '__meta__': {'code.md': b'# Code\n', 'code.structure.json': structure_spec},
                'code': {'guide.md': guide, 'intro.md': intro},
            }
        }
    )


def _budget(tokens: int) -> bytes:
    """A structure specification that sets a token budget and nothing else.

    Args:
        tokens: The most tokens the specification lets a document it governs hold; at least 1.
    """
    return f'{{"tokens": {tokens}}}'.encode()


@pytest.fixture(scope='module')
def package_table() -> RuleTable:
    """The rule table of the package's own rules at their default levels; immutable, so shared by the module."""
    return RuleTable.from_registry(package_registry())


@pytest.fixture(scope='module')
def sample_table() -> RuleTable:
    """The rule table of the sample rules this module declares, one at each level; immutable, so shared by the module.

    The registry holds the sample rules as it would hold any rule, so they reach the runner through the table alone.
    """
    return RuleTable.from_registry(Registry((OverHalfBudget, EmptyDocument, AnyTokens)))


@pytest.mark.it
class TestCheckSubjects:
    def test_check_subjects_with_a_document_over_its_budget_reports_the_token_budget_as_an_error(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(_budget(5), guide=GUIDE_TEXT.encode()))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        occurrence = TooManyTokens(
            spec=CODE_SPEC, line=LineNumber.from_int(1), token_count=count_tokens(GUIDE_TEXT), budget=5
        )
        assert reports == (
            CheckedSubject(GUIDE, diagnostics=(RuleDiagnostic(GUIDE.path, occurrence, Severity.ERROR),), ungoverned=()),
        ), 'LEN001 runs at deny, so a document over its budget carries its occurrence as an error'

    def test_check_subjects_with_a_document_within_its_budget_reports_it_clean(self, package_table: RuleTable) -> None:
        #: Given
        database = Database(_snapshot(_budget(1000), guide=GUIDE_TEXT.encode()))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        assert reports == (CheckedSubject(GUIDE, diagnostics=(), ungoverned=()),), (
            'a governed document within its budget has no diagnostic and no ungoverned input'
        )

    def test_check_subjects_with_no_budget_set_reports_the_token_count_as_ungoverned(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(b'{"empty_sections": "forbidden"}', guide=GUIDE_TEXT.encode()))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        assert reports == (CheckedSubject(GUIDE, diagnostics=(), ungoverned=(InputKind.TOKEN_COUNT,)),), (
            'no specification sets a budget, which is coverage, not a diagnostic'
        )

    def test_check_subjects_with_a_document_in_no_corpus_reports_the_token_count_as_ungoverned(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        # the code corpus sets a budget, but `docs/blog/` has no corpus spec, so the model holds no `blog` corpus
        snapshot = Snapshot.from_tree(
            {
                'docs': {
                    '__meta__': {'code.md': b'# Code\n', 'code.structure.json': _budget(5)},
                    'blog': {'launch.md': GUIDE_TEXT.encode()},
                }
            }
        )
        database = Database(snapshot)
        launch = DocumentRef(CorpusName.parse('blog'), AspectFilename.parse('launch'))

        #: When
        reports = check_subjects(database, (launch,), package_table)

        #: Then
        assert reports == (CheckedSubject(launch, diagnostics=(), ungoverned=(InputKind.TOKEN_COUNT,)),), (
            'no specification governs a document in no corpus the model holds, which is coverage, not a diagnostic'
        )

    def test_check_subjects_with_an_undecodable_document_reports_it_undecodable(self, package_table: RuleTable) -> None:
        #: Given
        database = Database(_snapshot(_budget(1000), guide=b'# Caf\xe9\n'))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        assert reports == (UndecodableSubject(GUIDE),), 'a document that is not UTF-8 is judged by no rule'

    def test_check_subjects_with_an_undecodable_ungoverned_document_reports_it_undecodable(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(b'{"empty_sections": "forbidden"}', guide=b'# Caf\xe9\n'))

        #: When
        reports = check_subjects(database, (GUIDE,), package_table)

        #: Then
        assert reports == (UndecodableSubject(GUIDE),), (
            'a document is decoded before governance is read, so it is undecodable whatever governs it'
        )

    def test_check_subjects_with_several_documents_reports_them_in_the_order_given(
        self, package_table: RuleTable
    ) -> None:
        #: Given
        database = Database(_snapshot(_budget(1000), guide=GUIDE_TEXT.encode()))

        #: When
        reports = check_subjects(database, (INTRO, GUIDE), package_table)

        #: Then
        assert [report.ref for report in reports] == [INTRO, GUIDE], 'each document is reported in the order given'

    def test_check_subjects_with_no_enabled_rule_over_the_token_count_never_counts_the_tokens(self) -> None:
        #: Given
        database = CountingDatabase(_snapshot(_budget(5), guide=GUIDE_TEXT.encode()))
        severities: dict[type[Rule], Severity] = {}
        table = RuleTable(severities)

        #: When
        check_subjects(database, (GUIDE,), table)

        #: Then
        assert database.counted == [], 'an input no enabled rule reads is never built, so its query is never asked'

    def test_check_subjects_with_sample_rules_reports_each_at_its_level(self, sample_table: RuleTable) -> None:
        #: Given
        # a budget the document holds more than half of, and less than all of
        token_count_of_guide = count_tokens(GUIDE_TEXT)
        database = Database(_snapshot(_budget(token_count_of_guide + 1), guide=GUIDE_TEXT.encode()))

        #: When
        reports = check_subjects(database, (GUIDE,), sample_table)

        #: Then
        over_half = OverHalfBudget(
            spec=CODE_SPEC,
            line=LineNumber.from_int(1),
            token_count=token_count_of_guide,
            budget=token_count_of_guide + 1,
        )
        any_tokens = AnyTokens(spec=None, line=LineNumber.from_int(1), token_count=token_count_of_guide)
        assert reports == (
            CheckedSubject(
                GUIDE,
                diagnostics=(
                    RuleDiagnostic(GUIDE.path, any_tokens, Severity.ERROR),
                    RuleDiagnostic(GUIDE.path, over_half, Severity.WARNING),
                ),
                ungoverned=(),
            ),
        ), 'each sample rule runs at its level through the registry alone, the error sorted before the warning'

    def test_check_subjects_with_a_sample_rule_at_allow_never_runs_it(self, sample_table: RuleTable) -> None:
        #: Given
        # an empty document, which the sample rule at allow, empty-document, would report
        database = Database(_snapshot(_budget(10), guide=b''))

        #: When
        reports = check_subjects(database, (GUIDE,), sample_table)

        #: Then
        any_tokens = AnyTokens(spec=None, line=LineNumber.from_int(1), token_count=0)
        assert reports == (
            CheckedSubject(GUIDE, diagnostics=(RuleDiagnostic(GUIDE.path, any_tokens, Severity.ERROR),), ungoverned=()),
        ), 'a rule at allow is not in the table, so only the enabled rules report'
