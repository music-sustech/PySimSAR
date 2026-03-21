# Data Model: Version 0.1 Release Documentation

**Branch**: `003-release-docs` | **Date**: 2026-03-21

This document defines the structure of the documentation deliverable — the "data model" is the documentation architecture itself.

## Documentation Site Structure

### Entity: Documentation Chapter

A self-contained Markdown file covering one topic.

| Field | Description |
|-------|-------------|
| `title` | Chapter heading (H1) |
| `nav_position` | Order in MkDocs navigation |
| `content_type` | One of: tutorial, reference, explanation, how-to |
| `body` | Narrative Markdown content |
| `code_examples` | Optional embedded runnable code blocks |
| `diagrams` | Optional Mermaid or PNG diagrams |
| `cross_references` | Links to related chapters |

### Entity: Math Section

A subsection within `math/*.md` files documenting one algorithm.

| Field | Description |
|-------|-------------|
| `algorithm_name` | Canonical name (e.g., "Range-Doppler Algorithm") |
| `code_module` | Corresponding Python module path (e.g., `pySimSAR.algorithms.image_formation.range_doppler`) |
| `signal_model` | LaTeX equations for the mathematical formulation |
| `derivation_steps` | 2-3 key intermediate steps |
| `final_result` | The implemented equation with variable definitions |
| `notation_mapping` | Rows for the notation table (symbol → code variable) |
| `references` | Literature citations (author, year, title) |
| `supported_modes` | Which SAR modes the algorithm supports |

### Entity: API Entry

A reference entry for one public class or function.

| Field | Description |
|-------|-------------|
| `class_name` | Fully qualified name (e.g., `pySimSAR.core.radar.Radar`) |
| `description` | One-paragraph purpose statement |
| `constructor_params` | List of (name, type, default, description) |
| `public_methods` | List of (name, signature, return_type, description) |
| `properties` | List of (name, type, description) |
| `usage_example` | Optional code snippet |
| `see_also` | Cross-references to related classes |

### Entity: Configuration Example

A complete, runnable JSON or Python snippet.

| Field | Description |
|-------|-------------|
| `title` | Descriptive title |
| `context` | Which chapter/section it belongs to |
| `format` | JSON or Python |
| `content` | The code/config content |
| `expected_output` | What the user should see when running it |
| `prerequisites` | Any setup needed (e.g., "requires default_stripmap preset") |

## Chapter Inventory

The following chapters map to spec requirements:

| Chapter File | FR | Content Type | Priority |
|-------------|-----|--------------|----------|
| `index.md` | FR-013 | Overview | P1 |
| `getting-started.md` | FR-002 | Tutorial | P1 |
| `architecture.md` | FR-001, FR-012 | Explanation | P1 |
| `data-structures.md` | FR-003 | Reference | P1 |
| `configuration.md` | FR-004 | Reference | P1 |
| `math/signal-model.md` | FR-005a,b | Explanation | P2 |
| `math/image-formation.md` | FR-005c | Explanation | P2 |
| `math/motion-compensation.md` | FR-005d | Explanation | P2 |
| `math/autofocus.md` | FR-005e | Explanation | P2 |
| `math/geocoding.md` | FR-005f | Explanation | P2 |
| `math/polarimetry.md` | FR-005g | Explanation | P2 |
| `math/notation.md` | FR-011 | Reference | P2 |
| `customization/scripting.md` | FR-006e | How-to | P2 |
| `customization/algorithms.md` | FR-006a,b | How-to | P2 |
| `customization/waveforms.md` | FR-006c | How-to | P2 |
| `customization/sensors.md` | FR-006d | How-to | P2 |
| `api/core.md` | FR-007 | Reference | P3 |
| `api/simulation.md` | FR-007 | Reference | P3 |
| `api/algorithms.md` | FR-007 | Reference | P3 |
| `api/io.md` | FR-007 | Reference | P3 |
| `api/pipeline.md` | FR-007 | Reference | P3 |
| `known-issues.md` | FR-008 | Reference | P1 |
| `changelog.md` | FR-013 | Reference | P1 |

## API Reference Class Inventory (~25 key classes)

### Core (7 classes)
1. `Radar` — Radar system model
2. `AntennaPattern` — 2D antenna gain pattern
3. `Scene` — Target container
4. `PointTarget` — Point scatterer
5. `DistributedTarget` — Extended target
6. `Platform` — Aircraft/UAV platform
7. `SARCalculator` — Derived parameter calculator

### Types (5 types)
8. `SARModeConfig` — Imaging mode configuration
9. `RawData` — Raw echo data container
10. `PhaseHistoryData` — Range-compressed data
11. `SARImage` — Focused image product
12. `SimulationState` — Lifecycle enum

### Simulation (2 classes)
13. `SimulationEngine` — Pulse-loop echo generation
14. `SimulationConfig` — Simulation parameters + state machine

### Algorithms (8 classes — one per algorithm family representative + registries)
15. `ImageFormationAlgorithm` — Base class for all IFA
16. `RangeDopplerAlgorithm` — RDA implementation
17. `MotionCompensationAlgorithm` — Base class for MoCo
18. `AutofocusAlgorithm` — Base class for autofocus
19. `ImageTransformationAlgorithm` — Base class for geocoding
20. `PolarimetricDecomposition` — Base class for polarimetry
21. `AlgorithmRegistry` — Generic registry

### IO (3 classes)
22. `ProcessingConfig` — Processing pipeline configuration
23. `write_hdf5` / `read_hdf5` — HDF5 I/O functions
24. `ParameterSet` — JSON parameter loading with $ref resolution

### Pipeline (1 class)
25. `PipelineRunner` — Sequential processing orchestrator

### Waveforms (2 classes)
26. `LFMWaveform` — Linear FM chirp
27. `FMCWWaveform` — FMCW continuous wave

**Total**: 27 key entries (slightly over ~25 target — all essential)

## Notation Table Structure

The notation table (`math/notation.md`) maps between mathematical symbols and code:

| Symbol | Description | Code Variable | Module |
|--------|-------------|---------------|--------|
| $f_c$ | Carrier frequency | `carrier_freq` | `core.radar` |
| $B$ | Bandwidth | `bandwidth` | `waveforms.base` |
| $K_r$ | Chirp rate / slope | `chirp_rate` | `waveforms.lfm` |
| $R$ | Slant range | `slant_range` | `simulation.signal` |
| $\tau$ | Fast time (range) | `fast_time` | `simulation.signal` |
| $\eta$ | Slow time (azimuth) | `slow_time` | `simulation.engine` |
| ... | (expanded in implementation) | ... | ... |
