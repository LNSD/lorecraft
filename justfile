# Display available commands and their descriptions (default target)
default:
    @just --list


## Workspace management

alias setup := sync

# Sync the development environment: the package and every group (uv sync --all-groups)
[group: 'workspace']
sync:
    @echo "🚀 Setting up development environment..."
    uv sync --all-groups

# Remove build, test and cache artifacts
[group: 'workspace']
clean:
    @echo "🧹 Cleaning build and test artifacts..."
    rm -rf .pytest_cache/ .ruff_cache/ dist/
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete


## Code formatting and linting

alias format := fmt

# Format Python code (ruff format)
[group: 'format']
fmt *EXTRA_FLAGS:
    @echo "✨ Formatting code..."
    uv run ruff format . {{EXTRA_FLAGS}}

alias format-check := fmt-check

# Check formatting without writing (ruff format --check)
[group: 'format']
fmt-check *EXTRA_FLAGS:
    @echo "✨ Checking formatting..."
    uv run ruff format --check . {{EXTRA_FLAGS}}


## Check

alias lint := check

# Check Python code (ruff check), then the import layering (lint-imports)
[group: 'check']
check *EXTRA_FLAGS:
    @echo "🔍 Linting code..."
    uv run ruff check . {{EXTRA_FLAGS}}
    uv run lint-imports

alias lint-fix := check-fix

# Check and auto-apply the mechanical fixes (ruff check --fix)
[group: 'check']
check-fix *EXTRA_FLAGS:
    @echo "🔍 Linting code (with fixes)..."
    uv run ruff check . --fix {{EXTRA_FLAGS}}

alias check-types := typecheck

# Type-check the package source (ty check)
[group: 'check']
typecheck *EXTRA_FLAGS:
    @echo "🔍 Type-checking code..."
    uv run ty check src {{EXTRA_FLAGS}}


## Docs

# Each check exits 0 when clean and 1 when it reports findings. just runs each
# line in its own shell and stops at the first non-zero exit, so a findings exit
# fails the recipe; fix what the first check reports, then rerun for the rest.

# Check this repository's own documents with every lorecraft check
[group: 'docs']
check-docs *EXTRA_FLAGS:
    @echo "📚 Checking documents..."
    uv run lorecraft check {{EXTRA_FLAGS}}

# Check this repository's own skills against the Agent Skills specification (check_skill)
[group: 'docs']
check-skills *EXTRA_FLAGS:
    @echo "📚 Checking skills..."
    .agents/skills/skills-check/scripts/check_skill.py {{EXTRA_FLAGS}}


## Codegen

GEN_SCHEMAS_OUTDIR := "docs/schemas"

# Run all code generation tasks
[group: 'codegen']
gen: gen-schemas

# Generate the JSON Schemas of the package's pydantic models into docs/schemas/ (pydantic, in a uv script)
[group: 'codegen']
gen-schemas:
    #!/usr/bin/env -S uv run python
    # Runs in the workspace environment: run `just sync` first.
    #
    # Each schema is rendered from the pydantic model the package deserializes the file with, so the schema an
    # editor applies and the validation the check runs come from one declaration; nothing here restates a field.
    # The models carry everything an editor is shown: descriptions as field docstrings, examples and bounds in
    # `Field`, titles and whole examples in `model_config`.
    import json
    from pathlib import Path

    from pydantic import BaseModel
    from pydantic.json_schema import GenerateJsonSchema

    from lorecraft.project.schemas import (
        SkillFrontmatter,
        StructureFile,
    )

    JSON_SCHEMA_DIALECT = 'https://json-schema.org/draft/2020-12/schema'


    class WithoutPropertyTitles(GenerateJsonSchema):
        """pydantic's generator, without the title it gives every property: a property's key already names it."""

        def field_title_should_be_set(self, schema: object) -> bool:
            return False


    def unwrap_descriptions(node: object) -> None:
        """Rejoin the lines each description's docstring was wrapped at, keeping its paragraph breaks: an editor
        wraps the text to its own width."""
        if isinstance(node, dict):
            for key, value in node.items():
                if key == 'description' and isinstance(value, str):
                    paragraphs = value.split('\n\n')
                    node[key] = '\n\n'.join(' '.join(paragraph.split()) for paragraph in paragraphs)
                else:
                    unwrap_descriptions(value)
        elif isinstance(node, list):
            for item in node:
                unwrap_descriptions(item)


    def write_schema(file_model: type[BaseModel], filename: str) -> None:
        """Write one file model's JSON Schema, led by the dialect it is written in, and print where it went."""
        schema = file_model.model_json_schema(schema_generator=WithoutPropertyTitles)
        unwrap_descriptions(schema)
        path = Path('{{GEN_SCHEMAS_OUTDIR}}') / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        document = {'$schema': JSON_SCHEMA_DIALECT, **schema}
        path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(f'  {path}')


    print('Generating the specification schemas...')
    write_schema(StructureFile, 'structure.spec.json')
    write_schema(SkillFrontmatter, 'skill-frontmatter.spec.json')


## Build

# Build the source distribution and the wheel (uv build)
[group: 'build']
build:
    @echo "📦 Building"
    uv build


## Test

alias test-all := test

# Run the whole test suite (pytest)
[group: 'test']
test *EXTRA_FLAGS:
    @echo "🎯 Running tests..."
    uv run pytest {{EXTRA_FLAGS}}

# Run unit tests (fast, no external dependencies)
[group: 'test']
test-unit *EXTRA_FLAGS: (test "-m" "unit" EXTRA_FLAGS)

# Run integration tests (the package's own modules wired together, in process)
[group: 'test']
test-it *EXTRA_FLAGS: (test "-m" "it" EXTRA_FLAGS)

# Run end-to-end tests (the installed console script, in a subprocess)
[group: 'test']
test-e2e *EXTRA_FLAGS: (test "-m" "e2e" EXTRA_FLAGS)

# Snapshot tests compare output to checked-in files under `__snapshots__/`; every `test` recipe fails on a
# mismatch and on a snapshot no test reads any more. Update over the whole suite, never one tier: a snapshot
# of a deselected test would read as unused.

# Write or refresh every snapshot and delete the unused ones (pytest --snapshot-update)
[group: 'test']
snapshot-update *EXTRA_FLAGS: (test "--snapshot-update" EXTRA_FLAGS)

# Show what the snapshots changed since the last commit: the review before committing them
[group: 'test']
snapshot-review:
    @git status --short -- ':(glob)**/__snapshots__/**'
    @git diff -- ':(glob)**/__snapshots__/**'


## Misc

PRECOMMIT_CONFIG := ".github/pre-commit-config.yaml"
PRECOMMIT_DEFAULT_HOOKS := "pre-commit pre-push"

# Install Git hooks
[group: 'misc']
install-git-hooks HOOKS=PRECOMMIT_DEFAULT_HOOKS:
    #!/usr/bin/env bash
    set -e # Exit on error

    # Check if pre-commit is installed
    if ! command -v "pre-commit" &> /dev/null; then
        >&2 echo "=============================================================="
        >&2 echo "Required command 'pre-commit' not available ❌"
        >&2 echo ""
        >&2 echo "Please install pre-commit using your preferred package manager"
        >&2 echo "  uv tool install pre-commit"
        >&2 echo "  pipx install pre-commit"
        >&2 echo "  pacman -S pre-commit"
        >&2 echo "  brew install pre-commit"
        >&2 echo "=============================================================="
        exit 1
    fi

    # Install all Git hooks (see PRECOMMIT_DEFAULT_HOOKS for default hooks)
    pre-commit install --config {{PRECOMMIT_CONFIG}} {{replace_regex(HOOKS, "\\s*([a-z-]+)\\s*", "--hook-type $1 ")}}

# Run the Git hooks over every file, without committing
[group: 'misc']
run-git-hooks *EXTRA_FLAGS:
    #!/usr/bin/env bash
    set -e # Exit on error

    # Check if pre-commit is installed
    if ! command -v "pre-commit" &> /dev/null; then
        >&2 echo "=============================================================="
        >&2 echo "Required command 'pre-commit' not available ❌"
        >&2 echo ""
        >&2 echo "Please install pre-commit using your preferred package manager"
        >&2 echo "  uv tool install pre-commit"
        >&2 echo "  pipx install pre-commit"
        >&2 echo "  pacman -S pre-commit"
        >&2 echo "  brew install pre-commit"
        >&2 echo "=============================================================="
        exit 1
    fi

    # Every hook, including the pre-push ones, over the whole tree
    pre-commit run --config {{PRECOMMIT_CONFIG}} --all-files --hook-stage manual {{EXTRA_FLAGS}}

# Remove Git hooks
[group: 'misc']
remove-git-hooks HOOKS=PRECOMMIT_DEFAULT_HOOKS:
    #!/usr/bin/env bash
    set -e # Exit on error

    # Check if pre-commit is installed
    if ! command -v "pre-commit" &> /dev/null; then
        >&2 echo "=============================================================="
        >&2 echo "Required command 'pre-commit' not available ❌"
        >&2 echo ""
        >&2 echo "Please install pre-commit using your preferred package manager"
        >&2 echo "  uv tool install pre-commit"
        >&2 echo "  pipx install pre-commit"
        >&2 echo "  pacman -S pre-commit"
        >&2 echo "  brew install pre-commit"
        >&2 echo "=============================================================="
        exit 1
    fi

    # Remove all Git hooks (see PRECOMMIT_DEFAULT_HOOKS for default hooks)
    pre-commit uninstall --config {{PRECOMMIT_CONFIG}} {{replace_regex(HOOKS, "\\s*([a-z-]+)\\s*", "--hook-type $1 ")}}
