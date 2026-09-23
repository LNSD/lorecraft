# Display available commands and their descriptions (default target)
default:
    @just --list


## Workspace management

alias setup := sync

# Sync the development environment (uv sync --all-groups)
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

# Check Python code (ruff check)
[group: 'check']
check *EXTRA_FLAGS:
    @echo "🔍 Linting code..."
    uv run ruff check . {{EXTRA_FLAGS}}

alias lint-fix := check-fix

# Check and auto-apply the mechanical fixes (ruff check --fix)
[group: 'check']
check-fix *EXTRA_FLAGS:
    @echo "🔍 Linting code (with fixes)..."
    uv run ruff check . --fix {{EXTRA_FLAGS}}

alias check-types := typecheck

# Type-check the package (ty check)
[group: 'check']
typecheck *EXTRA_FLAGS:
    @echo "🔍 Type-checking code..."
    uv run ty check src/lorewright {{EXTRA_FLAGS}}


## Docs

# The check scripts exit 0 when clean and 1 when they report findings. just runs
# each line in its own shell and stops at the first non-zero exit, so a findings
# exit fails the recipe; fix what the first script reports, then rerun for the
# rest.

# Check this repository's own documents (check_header, check_structure, check_budget)
[group: 'docs']
check-docs *EXTRA_FLAGS:
    @echo "📚 Checking documents..."
    .agents/skills/docs-rules-check/scripts/check_header.py {{EXTRA_FLAGS}}
    .agents/skills/docs-rules-check/scripts/check_structure.py {{EXTRA_FLAGS}}
    .agents/skills/docs-rules-check/scripts/check_budget.py {{EXTRA_FLAGS}}

# Check this repository's own skills against the Agent Skills specification (check_skill)
[group: 'docs']
check-skills *EXTRA_FLAGS:
    @echo "📚 Checking skills..."
    .agents/skills/skills-check/scripts/check_skill.py {{EXTRA_FLAGS}}


## Build

# Build source distributions and wheels (uv build)
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
