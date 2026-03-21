# Feature Specification: Version 0.1 Release Documentation

**Feature Branch**: `003-release-docs`
**Created**: 2026-03-21
**Status**: Draft
**Input**: Comprehensive documentation for PySimSAR v0.1 release — program organization, internal workings, data structures, customization/programming guide, and mathematical principles of implemented algorithms.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First-Time User Orientation (Priority: P1)

A new user downloads PySimSAR v0.1 and wants to understand what the program does, how it is organized, and how to run their first SAR simulation. They need a clear getting-started guide that walks them through installation, launching the GUI, loading a preset scenario, running a simulation, and viewing the focused image.

**Why this priority**: Without onboarding documentation, new users cannot adopt the software at all. This is the minimum barrier to entry.

**Independent Test**: Can be tested by giving the documentation to a person with SAR domain knowledge but no prior exposure to PySimSAR, and verifying they can complete a full simulation workflow within 30 minutes.

**Acceptance Scenarios**:

1. **Given** a user has installed PySimSAR, **When** they read the Getting Started section, **Then** they can launch the GUI, load the default stripmap preset, run a simulation, and view the focused SAR image.
2. **Given** a user reads the Program Organization section, **When** they look at the package directory, **Then** they can identify which module handles each stage of the SAR processing pipeline.
3. **Given** a user encounters an error during simulation, **When** they consult the troubleshooting section, **Then** they find guidance on common issues and their resolution.

---

### User Story 2 - Understanding Data Structures and Configuration (Priority: P1)

An experienced SAR engineer wants to understand the data structures used in PySimSAR so they can configure custom radar parameters, define scenes with point and distributed targets, set up platform trajectories, and interpret simulation outputs (raw echo data, phase history, focused images). They need detailed reference documentation for every user-facing data type and configuration file format.

**Why this priority**: SAR engineers need to configure simulations precisely for their use cases. Without data structure documentation, they cannot move beyond the default presets.

**Independent Test**: Can be tested by giving the documentation to a SAR engineer and verifying they can create a custom simulation configuration from scratch (custom radar, scene, platform, and processing parameters) without reading the source code.

**Acceptance Scenarios**:

1. **Given** a user wants to configure a custom radar system, **When** they read the Radar Configuration section, **Then** they can set carrier frequency, bandwidth, waveform type, antenna pattern, polarization mode, and SAR imaging mode.
2. **Given** a user wants to define a multi-target scene, **When** they read the Scene Configuration section, **Then** they can create point targets with specified RCS values and positions, and distributed targets with reflectivity grids.
3. **Given** a user has completed a simulation, **When** they read the Output Data section, **Then** they understand the structure of HDF5 output files and can extract raw echo data, focused images, and trajectory information.
4. **Given** a user wants to configure the processing pipeline, **When** they read the Processing Configuration section, **Then** they can select image formation, motion compensation, autofocus, geocoding, and polarimetric decomposition algorithms with appropriate parameters.

---

### User Story 3 - Algorithm Mathematical Reference (Priority: P2)

A researcher or graduate student wants to understand the mathematical principles behind each algorithm implemented in PySimSAR — signal simulation, image formation, motion compensation, autofocus, geocoding, and polarimetric decomposition. They need equations, signal models, and references to foundational literature so they can validate simulation results against analytical expectations and extend the algorithms for their research.

**Why this priority**: Mathematical documentation distinguishes PySimSAR from a black box. Researchers need to trust and verify the implementation, and this documentation enables that.

**Independent Test**: Can be tested by verifying that a reader with graduate-level SAR knowledge can trace each algorithm from the mathematical description in the documentation to the corresponding code module, and confirm the equations match published references.

**Acceptance Scenarios**:

1. **Given** a user reads the Signal Simulation Mathematics section, **When** they examine the echo generation equations, **Then** they find the point-target response model, range equation, Doppler shift formulation, and antenna pattern integration — each with equation numbers and literature references.
2. **Given** a user reads the Image Formation Algorithms section, **When** they look at a specific algorithm (Range-Doppler, Chirp Scaling, or Omega-K), **Then** they find the processing steps expressed as mathematical operations with transfer functions, matched filters, and phase compensation terms.
3. **Given** a user reads the Autofocus section, **When** they examine PGA, MDA, Minimum Entropy, or PPP, **Then** they find the phase error estimation model, convergence criteria, and relevant citations.
4. **Given** a user reads the Polarimetry section, **When** they examine a decomposition algorithm, **Then** they find the scattering matrix formulation, decomposition equations, and physical interpretation of each component.

---

### User Story 4 - Customization and Programming Guide (Priority: P2)

A developer or advanced user wants to extend PySimSAR by writing custom algorithms (e.g., a new image formation method or autofocus technique), creating custom waveforms, adding new sensor models, or integrating PySimSAR into their own scripts and pipelines. They need a programming guide that explains the plugin/registry architecture, abstract base classes, and the conventions for extending each subsystem.

**Why this priority**: Extensibility is a core value proposition of an open-source SAR simulator. Without a programming guide, only the original developer can add new capabilities.

**Independent Test**: Can be tested by verifying that a developer can implement a new image formation algorithm following the guide, register it, and run it through the pipeline without modifying any existing source files.

**Acceptance Scenarios**:

1. **Given** a developer reads the Algorithm Extension Guide, **When** they follow the instructions for creating a new image formation algorithm, **Then** they can subclass the base class, implement required methods, register it in the algorithm registry, and use it in the processing pipeline.
2. **Given** a developer wants to script a batch simulation, **When** they read the Scripting Guide, **Then** they can write a standalone script that creates a scene, configures a radar, runs a simulation, processes the result, and saves the focused image — all without the GUI.
3. **Given** a developer reads the Waveform Extension Guide, **When** they follow the instructions, **Then** they can create a custom waveform class with generate() and range_compress() methods, register it, and use it in simulations.
4. **Given** a developer reads the Sensor Extension Guide, **When** they follow the instructions, **Then** they can create a custom GPS or IMU error model and use it for motion perturbation and navigation.

---

### User Story 5 - Complete API Reference (Priority: P3)

A power user wants a comprehensive reference of all public classes, methods, and their parameters. This serves as a lookup resource for day-to-day usage after the user has already learned the basics from other documentation sections.

**Why this priority**: API reference is valuable but is a complement to the narrative documentation. Users need the narrative guides first; the API reference serves as a quick-lookup companion.

**Independent Test**: Can be tested by selecting 10 random public classes/methods from the codebase and verifying each has a corresponding entry in the API reference with parameter descriptions and return types.

**Acceptance Scenarios**:

1. **Given** a user wants to look up a specific class, **When** they consult the API Reference, **Then** they find the class description, constructor parameters, public methods, and return types.
2. **Given** a user wants to understand the parameters of a specific algorithm, **When** they look up the algorithm in the API Reference, **Then** they find each parameter's name, type, default value, and description.

---

### Edge Cases

- What happens when the documentation references a feature that is not yet stable or has known bugs (e.g., PGA autofocus streaks, MoCo+GPS noise issues)? Known limitations should be documented transparently in a "Known Issues" section.
- What happens when a user follows the Getting Started guide on a system without all optional dependencies (e.g., PyQt6 not installed for headless use)? The documentation should distinguish between core library dependencies and GUI dependencies.
- What happens when the documentation references file paths or directory structures that differ between operating systems? Platform-specific notes should be included where relevant.
- What happens when equations in the mathematical reference use notation inconsistent with the code variable names? A notation table should map mathematical symbols to code identifiers.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Documentation MUST include a Program Organization chapter that describes the package structure, module responsibilities, and data flow from simulation through image formation to output.
- **FR-002**: Documentation MUST include a Getting Started chapter with installation instructions, first-run walkthrough, and a complete example using a shipped preset.
- **FR-003**: Documentation MUST include a Data Structures Reference chapter covering all user-facing types: SARModeConfig, RawData, PhaseHistoryData, SARImage, Scene/PointTarget/DistributedTarget, Radar/AntennaPattern, Platform/Trajectory, and configuration objects (SimulationConfig, ProcessingConfig).
- **FR-004**: Documentation MUST include a Configuration Guide chapter explaining the JSON parameter set system, preset loading, $ref/$data resolution, and HDF5 I/O format.
- **FR-005**: Documentation MUST include a Mathematical Principles chapter with key equations and brief derivation sketches (2-3 intermediate steps per algorithm) for: (a) SAR signal model and echo generation, (b) LFM and FMCW waveform models, (c) Range-Doppler, Chirp Scaling, and Omega-K image formation algorithms, (d) First-order and second-order motion compensation, (e) PGA, MDA, Minimum Entropy, and PPP autofocus algorithms, (f) Slant-to-ground and georeferencing transformations, (g) Pauli, Freeman-Durden, Yamaguchi, and Cloude-Pottier polarimetric decompositions.
- **FR-006**: Documentation MUST include a Customization and Programming Guide chapter explaining: (a) the algorithm registry and plugin architecture, (b) how to subclass and register new algorithms for each subsystem, (c) how to create custom waveforms, (d) how to create custom sensor error models, (e) how to script simulations without the GUI.
- **FR-007**: Documentation MUST include a hand-written API Reference chapter covering key public classes (~25 core types and algorithms) with parameter descriptions, types, and return values. Full auto-generated coverage is deferred to a future release.
- **FR-008**: Documentation MUST include a Known Issues and Limitations section listing current bugs and incomplete features with workarounds where available.
- **FR-009**: All mathematical equations MUST be typeset in LaTeX notation (using `$...$` for inline and `$$...$$` for display equations) so they render correctly in Markdown viewers and can be converted to PDF with standard tools.
- **FR-010**: Each mathematical equation MUST include a reference to the foundational publication or textbook where the formulation originates.
- **FR-011**: Documentation MUST include a notation table mapping mathematical symbols to code variable names for traceability between equations and implementation.
- **FR-012**: Documentation MUST include diagrams for: (a) the overall system architecture and data flow, (b) the processing pipeline stages, (c) the SAR imaging geometry.
- **FR-013**: Documentation MUST be versioned and clearly labeled as v0.1, with a changelog section for tracking future updates.

### Key Entities

- **Documentation Chapter**: A self-contained section of the documentation covering a specific topic (e.g., Program Organization, Mathematical Principles). Each chapter has a title, narrative content, optional diagrams, and optional code examples.
- **API Entry**: A reference entry for a public class or function, including description, parameters, return type, and usage example.
- **Equation Block**: A numbered mathematical equation with variable definitions, derivation context, and literature citation.
- **Configuration Example**: A complete, runnable JSON or code snippet that demonstrates a specific configuration or usage pattern.

## Clarifications

### Session 2026-03-21

- Q: What documentation tooling should be used for rendering LaTeX, navigation, and PDF conversion? → A: MkDocs with Material theme. Documentation Markdown files reside in `docs/` at repo root with a `mkdocs.yml` config. Files are browsable on GitHub natively and rendered as a polished site via `mkdocs build` / `mkdocs gh-deploy`.
- Q: What depth of mathematical treatment for the 15 algorithms? → A: Key equations plus brief derivation sketches (2-3 intermediate steps per algorithm), not just final formulas and not full textbook derivations.
- Q: How should the API reference be authored? → A: Hand-written for key public classes only (~25 core types and algorithms). Curated quality over auto-generated completeness for v0.1.

## Assumptions

- The target audience is SAR engineers, researchers, and graduate students with domain knowledge of radar remote sensing. The documentation does not need to teach SAR fundamentals from scratch, but should be self-contained enough that a reader familiar with basic SAR concepts can understand all features.
- The documentation will be built using MkDocs with the Material theme, with source files in `docs/` and configuration in `mkdocs.yml` at the repo root. LaTeX is rendered via the `pymdownx.arithmatex` extension with MathJax. The Markdown files are also directly browsable on GitHub.
- Code examples will use the public API as it exists in the current codebase (v0.1) — no speculative features.
- Diagrams will be created as embedded images or text-based diagrams (e.g., Mermaid) that render in standard Markdown viewers and MkDocs.
- The mathematical notation will follow standard SAR literature conventions (Cumming & Wong, Soumekh, Richards).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user with SAR domain knowledge can complete a full simulation workflow (install → configure → simulate → view image) within 30 minutes using only the documentation.
- **SC-002**: Key public classes (~25 core types and algorithms) have hand-written API reference entries with parameter descriptions, types, and return values.
- **SC-003**: Every implemented algorithm (3 image formation + 2 MoCo + 4 autofocus + 2 geocoding + 4 polarimetry = 15 algorithms) has a dedicated mathematical description with at least one literature reference.
- **SC-004**: A developer can implement and register a new image formation algorithm by following the Customization Guide without reading existing algorithm source code, within 1 hour.
- **SC-005**: All user-facing data structures (minimum 10 types) have complete reference entries including field descriptions, valid ranges, and usage examples.
- **SC-006**: The documentation includes at least 5 runnable code examples that can be copy-pasted and executed successfully against the shipped presets.
- **SC-007**: Known issues are documented with severity, affected use cases, and workarounds — covering at minimum the PGA autofocus streaks and MoCo+GPS noise issues.
