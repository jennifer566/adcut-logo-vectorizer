# Contributing

## Atomic commits

Each commit must contain one fix, feature, refactor, test-only change, or documentation change.

- Do not combine unrelated work because it happened during the same coding session.
- Keep the implementation and its directly related tests in the same commit.
- Include dependency and lockfile changes with the feature that requires them.
- Put unrelated cleanup, formatting, or documentation in separate commits.
- Before committing, inspect the staged diff with `git diff --staged`.
- Use `git add <specific paths>` or `git add -p` instead of staging every change automatically.

If a staged diff needs more than one commit subject to describe it accurately, split it before committing.

## Commit messages

Use a conventional commit subject:

```text
feat: recognize circular paths
fix: preserve holes during DXF export
test: cover invalid PDF uploads
docs: explain curve simplification
```

The commit-message hook checks the format. The subject should describe the single outcome of that commit.

## Pull requests

Use a short-lived branch and keep each pull request focused on one issue or closely related outcome. A pull request may contain multiple commits when each commit is independently understandable and all commits contribute to the same requested change.

Before opening a pull request, run:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Review the commit list as well as the combined diff. Split or reorder commits before merging when unrelated changes appear together.
