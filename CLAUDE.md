# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PySimSAR is a Python SAR raw signal simulator with modular processing algorithms.
It uses Spec-Driven Development with the Speckit framework and Claude Code integration.

## Project Rules

- **Linting:** Always run `ruff check . --fix` after modifying Python files.
- **Style:** We follow PEP8; no unused imports or variables in the final PR.
- **Complexity:** Keep cyclomatic complexity under 10 for signal processing functions.
- **Synchronized docs:** After modifying code, update the relevant spec/plan/task and docs.

## Development Workflow

Features are developed through the Speckit pipeline:

1. **Create feature branch**: `git checkout -b ###-feature-name` (e.g., `001-user-auth`)
2. `/speckit.specify` — Create feature specification → `specs/###-feature-name/spec.md`
3. `/speckit.clarify` — Clarify ambiguous requirements (optional)
4. `/speckit.plan` — Generate implementation plan → `plan.md`, `research.md`, `data-model.md`, `contracts/`
5. `/speckit.tasks` — Generate task list → `tasks.md`
6. `/speckit.analyze` — Cross-artifact consistency validation
7. `/speckit.implement` — Execute implementation
8. `/speckit.checklist` — Generate quality checklists
9. `/speckit.taskstoissues` — Convert tasks to GitHub issues

## Branch Conventions

- Branch format: `###-short-name` (zero-padded 3 digits, e.g., `001-user-auth`)
- Main branch for PRs: `main`
- Each feature gets a `specs/###-feature-name/` directory with all artifacts

## Task Format

```
- [ ] [TaskID] [P?] [Story?] Description with file path
```
- `[P]` = parallelizable
- Story labels: `[US1]`, `[US2]`, etc.
- Priorities: P1 (MVP), P2, P3

