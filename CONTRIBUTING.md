# Contributing

Agents and people: read [CLAUDE.md](CLAUDE.md) for how the project fits together, and pick work from [docs/STATUS.md](docs/STATUS.md).

## Branches

One branch per piece of work, named `<number>-short-branch-title`, for example `1-phase-0-kindling`.

## Commit messages

```
<type> - short, concise description

- what changed, one bullet per point
- another point
```

Types: `feature`, `fix`, `test`, `refactor`, `docs`, `chore`.

No co-author or attribution trailers.

## Before committing

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov
```
