# Feature Specification: Fix Open Issues

**Feature Branch**: `004-fix-open-issues`
**Created**: 2026-03-22
**Status**: Draft
**Input**: User description: "Resolve open issues: SecondOrderMoCo missing _align_nav_positions, PGA estimate_phase_error not implemented, fragile autofocus tests, spotlight MoCo PNR threshold"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Second-Order Motion Compensation Works End-to-End (Priority: P1)

A SAR engineer runs a stripmap simulation with Dryden turbulence and selects second-order motion compensation. The processing pipeline completes successfully and produces a focused image with measurable improvement over the uncompensated case.

**Why this priority**: This is a blocking bug — selecting second-order MoCo in any pipeline scenario causes an immediate crash (AttributeError), making the feature completely unusable.

**Independent Test**: Can be tested by running the `stripmap_rda_dryden_moco2` scenario end-to-end and verifying the pipeline completes without error and produces a focused SAR image.

**Acceptance Scenarios**:

1. **Given** a stripmap scenario configured with Dryden turbulence and second-order MoCo, **When** the processing pipeline runs, **Then** the pipeline completes without errors and produces a focused SAR image.
2. **Given** a stripmap scenario with second-order MoCo and PGA autofocus, **When** the processing pipeline runs, **Then** both MoCo and autofocus stages execute successfully.
3. **Given** any MoCo algorithm variant (first-order or second-order), **When** the pipeline invokes navigation alignment and trajectory fitting, **Then** the algorithm provides the required interface without errors.

---

### User Story 2 - PGA Autofocus Supports the Standard Autofocus Interface (Priority: P2)

A SAR engineer uses the Phase Gradient Autofocus algorithm through the standard autofocus interface. The algorithm provides phase error estimation through the same public method as other autofocus algorithms, enabling consistent usage and testing across all autofocus implementations.

**Why this priority**: This is a design gap — PGA works via its `focus()` method but does not implement the standard `estimate_phase_error()` interface, breaking polymorphic usage and causing test failures.

**Independent Test**: Can be tested by calling `estimate_phase_error()` on a PGA instance with phase history data and verifying it returns a phase error array of the correct shape.

**Acceptance Scenarios**:

1. **Given** a PGA autofocus instance and valid phase history data, **When** `estimate_phase_error()` is called, **Then** a phase error array with shape matching the azimuth dimension is returned.
2. **Given** any autofocus algorithm (PGA, MDA, MEA, PPP), **When** `estimate_phase_error()` is called with the same input data, **Then** each returns a valid phase error array without raising exceptions.

---

### User Story 3 - Autofocus Tests Are Robust and Reliable (Priority: P2)

A developer runs the autofocus test suite and all tests pass reliably. Tests for "does not degrade ideal data" use appropriate tolerances that account for the signal-to-noise characteristics of the test configuration, eliminating false failures while still catching genuine regressions.

**Why this priority**: Fragile tests erode developer confidence and slow down development. These tests fail intermittently due to SNR-sensitive thresholds, not actual bugs.

**Independent Test**: Can be tested by running the full autofocus test suite repeatedly and verifying all tests pass consistently.

**Acceptance Scenarios**:

1. **Given** ideal (noise-free) SAR data, **When** any autofocus algorithm is applied, **Then** the "does not degrade" test passes with a tolerance that accommodates the numerical noise floor of the test configuration.
2. **Given** SAR data with known fourth-order phase error, **When** MEA autofocus is applied, **Then** the test verifies improvement using metrics that are robust to the test SNR level.
3. **Given** the test suite is run 10 consecutive times, **When** all autofocus tests execute, **Then** no intermittent failures occur.

---

### User Story 4 - Spotlight MoCo Scenario Passes Reliably (Priority: P3)

A developer runs the spotlight Omega-K with Dryden turbulence and first-order MoCo scenario test. The test passes reliably with a threshold that reflects the expected performance for this challenging scenario geometry.

**Why this priority**: The current PNR threshold is marginally too high for spotlight geometry with Dryden perturbations, causing a consistent false failure. Adjusting the threshold ensures the test suite is trustworthy.

**Independent Test**: Can be tested by running the `spotlight_omegak_dryden_moco1` scenario test and verifying it passes.

**Acceptance Scenarios**:

1. **Given** a spotlight scenario with Dryden turbulence and first-order MoCo, **When** the scenario test runs, **Then** the MoCo PNR exceeds the defined threshold and the test passes.
2. **Given** all scenario tests are run together, **When** the full test suite executes, **Then** no scenario test fails due to marginal thresholds.

---

### Edge Cases

- What happens when SecondOrderMoCo is used without GPS data? The pipeline should raise a clear error indicating GPS navigation data is required.
- What happens when PGA `estimate_phase_error()` receives data with very few azimuth samples? The method should handle degenerate inputs gracefully.
- What happens when autofocus is applied to single-pixel data? The algorithm should return without modification rather than crash.
- What happens when MoCo PNR is exactly at the threshold boundary? Tests should use appropriate comparison operators to handle boundary cases.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support second-order motion compensation through the same pipeline interface as first-order, with no additional caller-side code required.
- **FR-002**: System MUST ensure all MoCo algorithm variants expose a consistent interface for navigation alignment, position smoothing, and trajectory fitting operations used by the pipeline.
- **FR-003**: PGA autofocus MUST implement the standard `estimate_phase_error()` interface, returning phase error estimates consistent with other autofocus algorithms.
- **FR-004**: Autofocus "does not degrade" tests MUST use tolerances calibrated to the test configuration's signal characteristics, preventing false failures while still detecting genuine regressions of 5 dB or more.
- **FR-005**: Scenario tests MUST use PNR thresholds that reflect the expected performance for each scenario's geometry and perturbation model, with documented rationale for each threshold value.
- **FR-006**: All autofocus algorithms (PGA, MDA, MEA, PPP) MUST be testable through a uniform interface without special-casing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All scenario tests including second-order MoCo scenarios complete successfully with focused images.
- **SC-002**: The full autofocus test suite passes on 10 consecutive runs with zero intermittent failures.
- **SC-003**: All scenario tests including spotlight MoCo scenarios pass reliably.
- **SC-004**: PGA `estimate_phase_error()` returns valid phase error arrays matching the expected shape for all test inputs.
- **SC-005**: No test in the suite raises AttributeError or NotImplementedError for any supported algorithm configuration.

## Assumptions

- The existing first-order MoCo implementation is correct and serves as the reference for interface design.
- PGA's internal phase error estimation logic is correct and can be adapted for the public interface.
- Adjusting test tolerances (rather than changing algorithm parameters) is the appropriate fix for SNR-sensitive tests, since the test configuration's power/range/antenna settings are intentionally modest.
- The spotlight MoCo PNR of ~8.2 represents correct algorithm behavior for this geometry; the threshold should be adjusted to match rather than trying to improve PNR.
- The historical platform start position issue (y=-5000 too far from targets for beam illumination) has been corrected in all integration tests via dynamic half-aperture centering. The unused `platform_params` fixture in conftest.py still has the old value but does not affect any tests.
