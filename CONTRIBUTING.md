# Contributing to signalpost

Thanks for considering a contribution. This project is small and opinionated
on purpose — `detect.py` reports facts, `planner.py` holds every heuristic,
`constants.py` holds every magic number. Keep that separation when you add
or change behavior.

## Setup

```bash
pip install -e ".[dev]"
pytest
```

`make test` / `make lint` run the same inside Docker if you'd rather not
install anything locally. `make smoke-docker` renders a real stack, brings
it up with docker compose, and waits for every component to report healthy
— run it if your change touches `deploy.py` or the templates under
`signalpost/templates/`.

## Before opening a PR

- `pytest -q` and `ruff check .` should both pass.
- If you change or add a heuristic, update the decision table in
  `README.md` and add an entry to `CHANGELOG.md` under `[Unreleased]`.
- Keep new magic numbers in `signalpost/constants.py` rather than inline.
- Prefer a focused PR over a large one — small, reviewable diffs get merged
  faster.

## Reporting bugs

Open a GitHub issue with the command you ran, what you expected, and what
happened instead. For security vulnerabilities, do **not** open a public
issue — see [SECURITY.md](SECURITY.md).
