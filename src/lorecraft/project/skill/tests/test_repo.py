"""The resources of a skill, listed and read through a view over a snapshot built in memory.

Every snapshot here is recorded the way a scan records one: each file's bytes, and each symlink as an entry of its
parent's listing with its target. The repository walks it through `VirtualFileSystem`, so no case reads the disk;
the errors the operating system raises are pinned by the integration tier.
"""

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Final

import pytest

from lorecraft.core.path import RootRelativePath
from lorecraft.vfs import DirEntry, EntryKind, Link, Listing, RootExit, Snapshot, TextDecodeError, VirtualFileSystem

from ..outside import OutsideSymlink
from ..ref import SkillLocation, SkillRef, SkillResourceLocation, SkillResourceRef
from ..repo import (
    Repository,
    SkillResource,
    SkillResourceDecodeError,
    SkillResourceListing,
    SkillResourceReadError,
    SkillsListing,
)

SKILL: Final[str] = '.agents/skills/review'
REVIEW: Final[SkillLocation] = SkillLocation(
    SkillRef(RootRelativePath.parse(SKILL)),
    resolves_to=RootRelativePath.parse(SKILL),
    file_resolves_to=RootRelativePath.parse(f'{SKILL}/SKILL.md'),
)
"""A skill in a regular directory, whose `SKILL.md` is no symlink."""


def _repository(files: Mapping[str, bytes], symlinks: Mapping[str, str]) -> Repository:
    """A repository over a snapshot holding these files and symlinks, as a scan would record them.

    Args:
        files: File bytes keyed by root-relative path.
        symlinks: Symlink targets keyed by root-relative path, each spelled from the symlink's own directory. The
            directory a symlink sits in must hold a file too, so the snapshot lists it.
    """
    files_snapshot = Snapshot.from_files({RootRelativePath.parse(path): data for path, data in files.items()})
    entries: dict[RootRelativePath, list[DirEntry]] = {}
    for listing in files_snapshot.listings:
        entries[listing.path] = list(listing.entries)
    links: list[Link] = []
    for path, target in symlinks.items():
        symlink = RootRelativePath.parse(path)
        entries[symlink.parent].append(DirEntry(symlink.name, EntryKind.SYMLINK))
        links.append(Link(symlink, PurePosixPath(target)))

    listings: list[Listing] = []
    for directory in sorted(entries):
        listed = sorted(entries[directory], key=lambda entry: entry.name)
        listings.append(Listing(directory, tuple(listed)))
    snapshot = Snapshot(
        listings=tuple(listings), files=files_snapshot.files, links=tuple(sorted(links, key=lambda link: link.path))
    )
    return Repository(VirtualFileSystem(snapshot))


def _outside(path: str, link: str, target: str) -> OutsideSymlink:
    """A symlink reached at `path` whose chain leaves the root through `link`, which targets `target`.

    Args:
        path: Where an agent reaches the symlink, root-relative.
        link: The link the chain leaves the root through, at its canonical path.
        target: That link's target, as recorded.
    """
    return OutsideSymlink(RootRelativePath.parse(path), RootExit(RootRelativePath.parse(link), PurePosixPath(target)))


def _resource(path: str, resolves_to: str | None = None) -> SkillResourceLocation:
    """The location of a resource of the `review` skill.

    Args:
        path: Where an agent reaches the resource, root-relative.
        resolves_to: The canonical file it leads to; `path` itself when omitted.
    """
    canonical = path if resolves_to is None else resolves_to
    return SkillResourceLocation(
        SkillResourceRef(REVIEW.ref, RootRelativePath.parse(path)), resolves_to=RootRelativePath.parse(canonical)
    )


@pytest.mark.unit
class TestRepositoryListSkillResources:
    def test_list_skill_resources_with_nested_markdown_files_returns_each_sorted_by_path(self) -> None:
        #: Given
        repository = _repository(
            {
                f'{SKILL}/SKILL.md': b'',
                f'{SKILL}/references/deep/b.md': b'',
                f'{SKILL}/references/a.md': b'',
                f'{SKILL}/guide.md': b'',
            },
            {},
        )

        #: When
        resources = repository.list_skill_resources(REVIEW).resources

        #: Then
        assert resources == (
            _resource(f'{SKILL}/guide.md'),
            _resource(f'{SKILL}/references/a.md'),
            _resource(f'{SKILL}/references/deep/b.md'),
        ), 'every Markdown file at any depth is a resource, each at its own canonical path, in path order'

    def test_list_skill_resources_with_only_the_top_level_skill_file_returns_empty(self) -> None:
        #: Given
        repository = _repository({f'{SKILL}/SKILL.md': b''}, {})

        #: When
        resources = repository.list_skill_resources(REVIEW).resources

        #: Then
        assert resources == (), 'the top-level SKILL.md is the skill itself, not one of its resources'

    def test_list_skill_resources_with_a_symlinked_top_level_skill_file_leaves_it_out(self) -> None:
        #: Given
        repository = _repository(
            {f'{SKILL}/references/a.md': b'', 'shared/review.md': b''},
            {f'{SKILL}/SKILL.md': '../../../shared/review.md'},
        )
        review = SkillLocation(
            REVIEW.ref, resolves_to=REVIEW.resolves_to, file_resolves_to=RootRelativePath.parse('shared/review.md')
        )

        #: When
        resources = repository.list_skill_resources(review).resources

        #: Then
        assert resources == (_resource(f'{SKILL}/references/a.md'),), (
            'the top-level SKILL.md is the skill itself even when it is a symlink to where its text lives'
        )

    def test_list_skill_resources_with_a_nested_skill_file_lists_it(self) -> None:
        #: Given
        repository = _repository({f'{SKILL}/SKILL.md': b'', f'{SKILL}/examples/SKILL.md': b''}, {})

        #: When
        resources = repository.list_skill_resources(REVIEW).resources

        #: Then
        assert resources == (_resource(f'{SKILL}/examples/SKILL.md'),), (
            'a SKILL.md below the top level is a resource like any'
        )

    def test_list_skill_resources_with_files_not_ending_in_md_leaves_them_out(self) -> None:
        #: Given
        repository = _repository(
            {
                f'{SKILL}/SKILL.md': b'',
                f'{SKILL}/scripts/run.py': b'',
                f'{SKILL}/assets/logo.png': b'',
                f'{SKILL}/notes.txt': b'',
            },
            {},
        )

        #: When
        resources = repository.list_skill_resources(REVIEW).resources

        #: Then
        assert resources == (), 'only a file whose name ends in .md is a resource'

    def test_list_skill_resources_with_a_symlinked_directory_names_its_resources_under_the_skill(self) -> None:
        #: Given
        repository = _repository(
            {f'{SKILL}/SKILL.md': b'', 'shared/guides/deeper/d.md': b''},
            {f'{SKILL}/guides': '../../../shared/guides'},
        )

        #: When
        resources = repository.list_skill_resources(REVIEW).resources

        #: Then
        assert resources == (_resource(f'{SKILL}/guides/deeper/d.md', 'shared/guides/deeper/d.md'),), (
            'the symlinked directory is entered: its resource is named through the symlink, and located where it lives'
        )

    def test_list_skill_resources_with_a_symlinked_markdown_file_records_the_file_it_leads_to(self) -> None:
        #: Given
        repository = _repository(
            {f'{SKILL}/SKILL.md': b'', 'notes/e.md': b''},
            {f'{SKILL}/notes.md': '../../../notes/e.md'},
        )

        #: When
        resources = repository.list_skill_resources(REVIEW).resources

        #: Then
        assert resources == (_resource(f'{SKILL}/notes.md', 'notes/e.md'),), (
            'the symlink is named where it sits in the skill, and located at the file it leads to'
        )

    def test_list_skill_resources_with_a_symlink_to_a_markdown_file_not_named_md_leaves_it_out(self) -> None:
        #: Given
        repository = _repository(
            {f'{SKILL}/SKILL.md': b'', 'notes/e.md': b''},
            {f'{SKILL}/notes': '../../../notes/e.md'},
        )

        #: When
        resources = repository.list_skill_resources(REVIEW).resources

        #: Then
        assert resources == (), 'an agent reaches the file as `notes`, so by its name it is no resource'

    def test_list_skill_resources_with_a_symlink_to_the_skills_directory_does_not_enter_it(self) -> None:
        #: Given
        # `up` leads to `.agents/skills`, which holds the skill itself and the `commit` skill beside it
        repository = _repository(
            {
                f'{SKILL}/SKILL.md': b'',
                f'{SKILL}/references/a.md': b'',
                '.agents/skills/commit/SKILL.md': b'',
                '.agents/skills/commit/guide.md': b'',
            },
            {f'{SKILL}/references/up': '../..'},
        )

        #: When
        resources = repository.list_skill_resources(REVIEW).resources

        #: Then
        assert resources == (_resource(f'{SKILL}/references/a.md'),), (
            "a directory holding the skill is never entered, so no other skill's resource is counted as this one's"
        )

    def test_list_skill_resources_with_a_symlink_back_to_the_skill_lists_each_resource_once(self) -> None:
        #: Given
        repository = _repository(
            {f'{SKILL}/SKILL.md': b'', f'{SKILL}/references/a.md': b''},
            {f'{SKILL}/references/up': '..'},
        )

        #: When
        resources = repository.list_skill_resources(REVIEW).resources

        #: Then
        assert resources == (_resource(f'{SKILL}/references/a.md'),), (
            'the skill directory was entered already, so the symlink back to it adds nothing'
        )

    def test_list_skill_resources_with_a_symlink_into_the_skill_names_the_resources_where_they_really_are(self) -> None:
        #: Given
        # `alias` sorts before `references`, so the symlink is met before the directory it leads to is entered
        repository = _repository(
            {f'{SKILL}/SKILL.md': b'', f'{SKILL}/references/a.md': b''},
            {f'{SKILL}/alias': 'references'},
        )

        #: When
        resources = repository.list_skill_resources(REVIEW).resources

        #: Then
        assert resources == (_resource(f'{SKILL}/references/a.md'),), (
            'every directory reached without a symlink is entered first, so the resource keeps its canonical name'
        )

    def test_list_skill_resources_with_a_symlink_to_a_deeper_directory_names_the_resources_where_they_really_are(
        self,
    ) -> None:
        #: Given
        # `alias` sorts before `references`, and leads two levels down, to a directory entered after it is met
        repository = _repository(
            {f'{SKILL}/SKILL.md': b'', f'{SKILL}/references/deep/b.md': b''},
            {f'{SKILL}/alias': 'references/deep'},
        )

        #: When
        resources = repository.list_skill_resources(REVIEW).resources

        #: Then
        assert resources == (_resource(f'{SKILL}/references/deep/b.md'),), (
            'the symlink waits until references/deep/ is entered by its canonical path, so the resource keeps that name'
        )

    def test_list_skill_resources_with_two_directories_linking_to_each_other_enters_each_once(self) -> None:
        #: Given
        # `shared/q/to-s` leads to `shared/s`, and `shared/s/to-q` back to `shared/q`
        repository = _repository(
            {f'{SKILL}/SKILL.md': b'', 'shared/q/a.md': b'', 'shared/s/b.md': b''},
            {
                f'{SKILL}/q': '../../../shared/q',
                'shared/q/to-s': '../s',
                'shared/s/to-q': '../q',
            },
        )

        #: When
        resources = repository.list_skill_resources(REVIEW).resources

        #: Then
        assert resources == (
            _resource(f'{SKILL}/q/a.md', 'shared/q/a.md'),
            _resource(f'{SKILL}/q/to-s/b.md', 'shared/s/b.md'),
        ), 'each canonical directory is entered once, so the walk ends, and each resource is listed once'

    def test_list_skill_resources_with_dangling_symlinks_leaves_them_out(self) -> None:
        #: Given
        repository = _repository(
            {f'{SKILL}/SKILL.md': b''},
            {f'{SKILL}/gone.md': 'missing.md', f'{SKILL}/gone': '../../../missing'},
        )

        #: When
        resources = repository.list_skill_resources(REVIEW).resources

        #: Then
        assert resources == (), 'a symlink that leads to nothing is left out without failing the listing'

    def test_list_skill_resources_with_a_symlink_leading_outside_the_root_records_it_and_lists_no_resource(
        self,
    ) -> None:
        #: Given
        # `take_snapshot` keeps a target outside the root absolute, and follows nothing behind it
        repository = _repository(
            {f'{SKILL}/SKILL.md': b''},
            {f'{SKILL}/outside': '/srv/guides', f'{SKILL}/outside.md': '/srv/guides/a.md'},
        )

        #: When
        listing = repository.list_skill_resources(REVIEW)

        #: Then
        assert listing == SkillResourceListing(
            resources=(),
            outside_symlinks=(
                _outside(f'{SKILL}/outside', f'{SKILL}/outside', '/srv/guides'),
                _outside(f'{SKILL}/outside.md', f'{SKILL}/outside.md', '/srv/guides/a.md'),
            ),
        ), 'a symlink leading outside the root, whatever its name, is recorded where it is reached, not followed'

    def test_list_skill_resources_with_a_symlink_climbing_above_the_root_records_it(self) -> None:
        #: Given
        repository = _repository({f'{SKILL}/SKILL.md': b''}, {f'{SKILL}/shared': '../../../../shared'})

        #: When
        listing = repository.list_skill_resources(REVIEW)

        #: Then
        assert listing.outside_symlinks == (_outside(f'{SKILL}/shared', f'{SKILL}/shared', '../../../../shared'),), (
            'a `..` climbing above the root leaves it as an absolute target does'
        )

    def test_list_skill_resources_with_a_chain_leaving_the_root_records_the_link_it_leaves_through(self) -> None:
        #: Given
        # `references -> ../../../hop`, and `hop -> /srv/refs` at the root
        repository = _repository(
            {f'{SKILL}/SKILL.md': b'', 'README.md': b''},
            {f'{SKILL}/references': '../../../hop', 'hop': '/srv/refs'},
        )

        #: When
        listing = repository.list_skill_resources(REVIEW)

        #: Then
        assert listing.outside_symlinks == (_outside(f'{SKILL}/references', 'hop', '/srv/refs'),), (
            'the symlink is named where an agent reaches it, and the link the chain leaves through is recorded'
        )

    def test_list_skill_resources_with_a_symlinked_skill_entry_names_the_resources_under_the_entry(self) -> None:
        #: Given
        # `.agents/skills/audit -> ../../skills/audit`: the walk starts where the entry leads
        repository = _repository(
            {'.agents/skills/README.md': b'', 'skills/audit/SKILL.md': b'', 'skills/audit/references/a.md': b''},
            {'.agents/skills/audit': '../../skills/audit'},
        )
        audit = SkillLocation(
            SkillRef(RootRelativePath.parse('.agents/skills/audit')),
            resolves_to=RootRelativePath.parse('skills/audit'),
            file_resolves_to=RootRelativePath.parse('skills/audit/SKILL.md'),
        )

        #: When
        resources = repository.list_skill_resources(audit).resources

        #: Then
        assert resources == (
            SkillResourceLocation(
                SkillResourceRef(audit.ref, RootRelativePath.parse('.agents/skills/audit/references/a.md')),
                resolves_to=RootRelativePath.parse('skills/audit/references/a.md'),
            ),
        ), 'the resource is named under the skill entry, and located under the directory the entry leads to'

    def test_list_skill_resources_with_a_linked_entry_and_a_symlink_to_its_skills_directory_does_not_enter_it(
        self,
    ) -> None:
        #: Given
        # the skill's canonical directory is `skills/audit`, so `.agents/skills` holds only the entry the skill is
        # named by
        repository = _repository(
            {
                'skills/audit/SKILL.md': b'',
                'skills/audit/references/a.md': b'',
                '.agents/skills/review/SKILL.md': b'',
                '.agents/skills/review/guide.md': b'',
            },
            {'.agents/skills/audit': '../../skills/audit', 'skills/audit/agents': '../../.agents/skills'},
        )
        audit = SkillLocation(
            SkillRef(RootRelativePath.parse('.agents/skills/audit')),
            resolves_to=RootRelativePath.parse('skills/audit'),
            file_resolves_to=RootRelativePath.parse('skills/audit/SKILL.md'),
        )

        #: When
        resources = repository.list_skill_resources(audit).resources

        #: Then
        assert resources == (
            SkillResourceLocation(
                SkillResourceRef(audit.ref, RootRelativePath.parse('.agents/skills/audit/references/a.md')),
                resolves_to=RootRelativePath.parse('skills/audit/references/a.md'),
            ),
        ), 'the skills directory holds the entry the skill is named by, so the review skill is never counted'


def _skill_at(directory: str, resolves_to: str | None = None) -> SkillLocation:
    """The location of a skill named at `directory`, whose `SKILL.md` is no symlink.

    Args:
        directory: Where the skill is named, root-relative.
        resolves_to: The canonical directory it leads to; `directory` itself when omitted.
    """
    canonical = directory if resolves_to is None else resolves_to
    return SkillLocation(
        SkillRef(RootRelativePath.parse(directory)),
        resolves_to=RootRelativePath.parse(canonical),
        file_resolves_to=RootRelativePath.parse(f'{canonical}/SKILL.md'),
    )


@pytest.mark.unit
class TestRepositoryListNamedSkills:
    def test_list_named_skills_with_a_skill_file_at_its_root_lists_the_directory_alone(self) -> None:
        #: Given
        repository = _repository({'skills/review/SKILL.md': b'', 'skills/review/nested/SKILL.md': b''}, {})
        directory = RootRelativePath.parse('skills/review')

        #: When
        listing = repository.list_named_skills(directory, directory)

        #: Then
        assert listing == SkillsListing(skills=(_skill_at('skills/review'),), outside_symlinks=()), (
            'a directory with a SKILL.md at its root is one skill, whatever it holds below'
        )

    def test_list_named_skills_without_a_skill_file_at_its_root_lists_each_skill_directly_inside(self) -> None:
        #: Given
        repository = _repository(
            {'skills/review/SKILL.md': b'', 'skills/lint/SKILL.md': b'', 'skills/README.md': b''}, {}
        )
        directory = RootRelativePath.parse('skills')

        #: When
        listing = repository.list_named_skills(directory, directory)

        #: Then
        assert listing == SkillsListing(
            skills=(_skill_at('skills/lint'), _skill_at('skills/review')), outside_symlinks=()
        ), 'a directory with no SKILL.md at its root is read as a skills directory, its skills in name order'

    def test_list_named_skills_through_a_link_names_each_skill_under_the_link(self) -> None:
        #: Given
        repository = _repository({'skills/review/SKILL.md': b''}, {'bundle': 'skills'})
        directory = RootRelativePath.parse('bundle')

        #: When
        listing = repository.list_named_skills(directory, RootRelativePath.parse('skills'))

        #: Then
        assert listing == SkillsListing(skills=(_skill_at('bundle/review', 'skills/review'),), outside_symlinks=()), (
            'the skill is named under the directory as spelled, and located where its files really are'
        )

    def test_list_named_skills_with_an_entry_linked_to_a_skill_names_it_by_the_entry(self) -> None:
        #: Given
        repository = _repository(
            {'skills/review/SKILL.md': b'', 'bundle/README.md': b''}, {'bundle/review': '../skills/review'}
        )
        directory = RootRelativePath.parse('bundle')

        #: When
        listing = repository.list_named_skills(directory, directory)

        #: Then
        assert listing == SkillsListing(skills=(_skill_at('bundle/review', 'skills/review'),), outside_symlinks=()), (
            "an entry linked to a skill directory is a skill named by the entry, as in an agent's skills directory"
        )

    def test_list_named_skills_with_a_skill_file_at_its_root_linked_outside_records_it_as_no_skill(self) -> None:
        #: Given
        repository = _repository(
            {'skills/review/notes.md': b'', 'skills/review/nested/SKILL.md': b''},
            {'skills/review/SKILL.md': '/srv/review.md'},
        )
        directory = RootRelativePath.parse('skills/review')

        #: When
        listing = repository.list_named_skills(directory, directory)

        #: Then
        assert listing == SkillsListing(
            skills=(),
            outside_symlinks=(_outside('skills/review/SKILL.md', 'skills/review/SKILL.md', '/srv/review.md'),),
        ), 'the SKILL.md at the root makes the directory one skill, and its link leaving the root makes it none'

    def test_list_named_skills_with_neither_a_skill_file_nor_a_skill_inside_lists_nothing(self) -> None:
        #: Given
        repository = _repository({'docs/code/logging.md': b'', 'docs/glossary.md': b''}, {})
        directory = RootRelativePath.parse('docs')

        #: When
        listing = repository.list_named_skills(directory, directory)

        #: Then
        assert listing == SkillsListing(skills=(), outside_symlinks=()), (
            'a directory holding no SKILL.md holds no skill'
        )


@pytest.mark.unit
class TestRepositoryFindSkillsDirExit:
    def test_find_skills_dir_exit_with_a_skills_directory_linked_outside_records_it(self) -> None:
        #: Given
        repository = _repository({'.claude/README.md': b''}, {'.claude/skills': '/srv/skills'})

        #: When
        outside = repository.find_skills_dir_exit(RootRelativePath.parse('.claude/skills'))

        #: Then
        assert outside == _outside('.claude/skills', '.claude/skills', '/srv/skills'), (
            'the skills directory is recorded as declared, with the link it leaves through'
        )

    def test_find_skills_dir_exit_with_a_skills_directory_linked_inside_returns_none(self) -> None:
        #: Given
        repository = _repository(
            {'.claude/README.md': b'', f'{SKILL}/SKILL.md': b''}, {'.claude/skills': '../.agents/skills'}
        )

        #: When
        outside = repository.find_skills_dir_exit(RootRelativePath.parse('.claude/skills'))

        #: Then
        assert outside is None, 'a skills directory linked to another in the repository does not lead outside'


@pytest.mark.unit
class TestRepositoryGetSkillResource:
    def test_get_skill_resource_with_a_location_behind_a_symlink_reads_the_canonical_file(self) -> None:
        #: Given
        # nothing is at the ref's own path: only the recorded canonical file can answer
        repository = _repository({'notes/e.md': b'# Notes\n'}, {})
        location = _resource(f'{SKILL}/notes.md', 'notes/e.md')

        #: When
        resource = repository.get_skill_resource(location)

        #: Then
        assert resource == SkillResource(location.ref, '# Notes\n'), (
            'the resource is read at its location, named by its ref'
        )

    def test_get_skill_resource_with_bytes_that_are_not_utf8_raises_skill_resource_decode_error(self) -> None:
        #: Given
        repository = _repository({f'{SKILL}/references/a.md': b'caf\xe9\n'}, {})
        location = _resource(f'{SKILL}/references/a.md')

        #: When
        with pytest.raises(SkillResourceDecodeError) as exc_info:
            repository.get_skill_resource(location)

        #: Then
        assert exc_info.value.ref == location.ref, 'the error names the resource that could not be decoded'
        assert isinstance(exc_info.value.source, TextDecodeError), 'its source is the failed decode'

    def test_get_skill_resource_with_no_file_at_its_location_raises_skill_resource_read_error(self) -> None:
        #: Given
        repository = _repository({f'{SKILL}/SKILL.md': b''}, {})
        location = _resource(f'{SKILL}/references/a.md')

        #: When
        with pytest.raises(SkillResourceReadError) as exc_info:
            repository.get_skill_resource(location)

        #: Then
        assert exc_info.value.ref == location.ref, 'the error names the resource that could not be read'
