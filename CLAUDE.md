# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PySimSAR is a Spec-Driven Development project using the Speckit framework (v0.3.0) with Claude Code integration. It is initialized from a Specify template and configured with PowerShell scripts.

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

## Key Directories

- `.specify/templates/` — Spec document templates (spec, plan, tasks, checklist, constitution, agent-file)
- `.specify/scripts/powershell/` — Operational scripts (create-new-feature, setup-plan, check-prerequisites, common utilities)
- `.specify/memory/constitution.md` — Project constitution (template state, needs customization via `/speckit.constitution`)
- `.claude/commands/` — All Speckit command definitions

## Template Resolution Priority

1. `.specify/templates/overrides/` (project-specific)
2. `.specify/presets/` (preset-provided)
3. `.specify/extensions/` (extension-provided)
4. `.specify/templates/` (core defaults)

## Task Format

```
- [ ] [TaskID] [P?] [Story?] Description with file path
```
- `[P]` = parallelizable
- Story labels: `[US1]`, `[US2]`, etc.
- Priorities: P1 (MVP), P2, P3

## Prerequisites

- PowerShell (cross-platform `pwsh`)
- Git
- Claude Code
