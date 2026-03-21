# Implementation Plan: Version 0.1 Release Documentation

**Branch**: `003-release-docs` | **Date**: 2026-03-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-release-docs/spec.md`

## Summary

Produce comprehensive documentation for the PySimSAR v0.1 release covering program organization, data structures, configuration, mathematical principles of all 15 implemented algorithms, a customization/programming guide, and a hand-written API reference for ~25 key classes. Documentation is authored as Markdown files in `docs/` using MkDocs with Material theme for LaTeX rendering and site generation.

## Technical Context

**Language/Version**: Python 3.14 (documented project), Markdown (documentation source)
**Primary Dependencies**: mkdocs-material, pymdownx (arithmatex for LaTeX/MathJax)
**Storage**: N/A (documentation files only)
**Testing**: Manual review; runnable code examples validated against shipped presets
**Target Platform**: GitHub (browsable .md files) + MkDocs static site (GitHub Pages)
**Project Type**: Documentation deliverable (no application code changes)
**Performance Goals**: N/A
**Constraints**: All equations in LaTeX; hand-written API reference for ~25 key classes; math depth = key equations + 2-3 derivation steps per algorithm
**Scale/Scope**: ~10 documentation chapters, 15 algorithm math sections, ~25 API entries, 5+ runnable examples

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Scientific Correctness | PASS | Documentation will include mathematical models with source references for all algorithms (FR-005, FR-010) |
| II. Library-First | PASS | Documentation covers Python library API before GUI; scripting guide demonstrates headless usage (FR-006e) |
| III. Test-First (TDD) | N/A | No application code is being written in this feature |
| IV. Performance-Aware | N/A | No application code is being written in this feature |
| V. Reproducibility | PASS | Documentation covers reproducible simulation configurations and seed control |
| VI. Modularization | PASS | Documentation covers the registry/plugin architecture and how to extend each subsystem independently (FR-006) |

**Gate result**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/003-release-docs/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (documentation structure model)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (documentation outline contracts)
│   └── doc-outline.md   # Table of contents and chapter contracts
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
docs/                           # MkDocs documentation source
├── index.md                    # Home page — project overview, quick links
├── getting-started.md          # Installation, first simulation walkthrough
├── architecture.md             # Program organization, module map, data flow
├── configuration.md            # JSON parameter sets, presets, HDF5 format
├── data-structures.md          # User-facing types reference
├── math/                       # Mathematical principles (split by domain)
│   ├── signal-model.md         # SAR signal model, echo generation, waveforms
│   ├── image-formation.md      # RDA, CSA, Omega-K
│   ├── motion-compensation.md  # First-order, second-order MoCo
│   ├── autofocus.md            # PGA, MDA, MEA, PPP
│   ├── geocoding.md            # Slant-to-ground, georeferencing
│   ├── polarimetry.md          # Pauli, Freeman-Durden, Yamaguchi, Cloude-Pottier
│   └── notation.md             # Symbol-to-code notation table
├── customization/              # Programming and extension guide
│   ├── scripting.md            # Headless simulation scripting
│   ├── algorithms.md           # Extending image formation, MoCo, autofocus
│   ├── waveforms.md            # Custom waveform creation
│   └── sensors.md              # Custom GPS/IMU error models
├── api/                        # Hand-written API reference
│   ├── core.md                 # Radar, Scene, Platform, Calculator, types
│   ├── simulation.md           # SimulationEngine, SimulationConfig, signal
│   ├── algorithms.md           # Image formation, MoCo, autofocus, geocoding, polarimetry
│   ├── io.md                   # HDF5, ParameterSet, archive, config
│   └── pipeline.md             # PipelineRunner, ProcessingConfig
├── known-issues.md             # Known bugs, limitations, workarounds
├── changelog.md                # Version history
└── assets/                     # Diagrams, images
    └── sar-geometry.png

mkdocs.yml                      # MkDocs configuration at repo root
```

**Structure Decision**: Documentation split into topic-focused chapters with math and customization sections in subdirectories to keep navigation manageable. The `math/` subdirectory isolates the equation-heavy content. The `api/` subdirectory groups API reference by subsystem. Diagrams stored in `docs/assets/`.

## Complexity Tracking

No constitution violations — no complexity justifications needed.
