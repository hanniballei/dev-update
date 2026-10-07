# Repository Guidelines

## Project Structure & Module Organization

`SKILL.md` is the skill entry point. Executable helpers live in `scripts/`, tests in
`tests/`, and on-demand documentation in `references/`. Keep only entry points and
project configuration at the root. Runtime helpers use Python's standard library.

## Build, Test, and Development Commands

Run commands from the repository root. Set up development tools with
`python3 -m venv .venv` and
`.venv/bin/python -m pip install -r requirements-dev.txt`.
Verify with `.venv/bin/ruff check scripts tests`,
`.venv/bin/ruff format --check scripts tests`, and
`python3 -m unittest discover -s tests -v`. The default
`python3 scripts/npm_update.py` checks without installing packages; `--apply` requires
an actual request to update. See `README.md` for usage and environment requirements.

## Coding Style & Naming Conventions

Use descriptive, lowercase filenames; prefer `kebab-case` for Markdown documents
and the chosen language's standard convention for code. In Markdown, use ATX headings
(`## Heading`) and fenced code blocks with a language identifier. Introduce a
formatter or linter with the first code contribution, document its command, and
format only files touched by the change.

## Testing Guidelines

Use standard-library `unittest` with mocked subprocesses under `tests/`. Tests have
no production access and must not upgrade live packages or restart services. Add
focused coverage for new behavior and meaningful failure cases. Include the test
command and its result in each pull request.

## Commit & Pull Request Guidelines

This directory has no Git history, so no established commit message convention is
available. Use a short imperative subject, such as `Add update summary script`.
Pull requests should explain the change, link any related issue, and list the checks
run. Include screenshots when a change affects a visual interface.

## Configuration & Secrets

Document required environment variables in `README.md` and keep credentials in
local environment configuration or a secret manager. Commit example configuration
with placeholder values when setup needs illustration.
