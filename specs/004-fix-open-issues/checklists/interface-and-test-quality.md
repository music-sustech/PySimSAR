# Interface & Test Quality Checklist: Fix Open Issues

**Purpose**: Validate requirements quality for interface consistency, test robustness, and regression prevention across the four bug fixes
**Created**: 2026-03-22
**Feature**: [spec.md](../spec.md)
**Depth**: PR review gate
**Focus**: Interface consistency + Test robustness + Regression prevention

## Interface Consistency — Requirement Completeness

- [ ] CHK001 Is the shared interface contract for MoCo algorithms explicitly defined (method signatures, return types, preconditions), or only implied by "consistent interface"? [Clarity, Spec §FR-002]
- [ ] CHK002 Are the requirements for `estimate_phase_error()` return value semantics specified (units, reference convention, mean-removal) beyond just shape? [Clarity, Spec §FR-003]
- [ ] CHK003 Does the spec define what "consistent with other autofocus algorithms" means for PGA's `estimate_phase_error()` output — same numerical behavior, or just same shape/type contract? [Ambiguity, Spec §FR-003]
- [ ] CHK004 Are requirements documented for how future MoCo algorithms (third-order, etc.) should integrate with the pipeline without coupling? [Coverage, Gap]
- [ ] CHK005 Is the separation of concerns between pipeline trajectory reconstruction and MoCo compensation stated as a requirement, or only as a design decision in plan.md? [Traceability, Spec §FR-002 vs Plan §Fix-1]

## Interface Consistency — Scenario Coverage

- [ ] CHK006 Are acceptance scenarios defined for all MoCo + autofocus combinations (moco1+PGA, moco2+PGA, moco1+MDA, moco2+MDA, etc.)? [Coverage, Spec §US1]
- [ ] CHK007 Is the PGA `estimate_phase_error()` tested with corrupted data (not just ideal), to verify it produces meaningful phase errors? [Coverage, Spec §US2]
- [ ] CHK008 Are requirements specified for `estimate_phase_error()` behavior when called on data that has already been autofocused? [Edge Case, Gap]

## Test Robustness — Requirement Clarity

- [ ] CHK009 Is the 5 dB tolerance for "does not degrade" tests derived from a documented analysis, or only justified qualitatively ("a broken algorithm degrades by 10+ dB")? [Measurability, Spec §FR-004]
- [ ] CHK010 Are the test configuration parameters (X-band, 100W, 30 dB gain, 5 km range) that drive tolerance selection documented as requirements, or only as assumptions? [Traceability, Spec §Assumptions]
- [ ] CHK011 Is the PNR threshold of 5 for spotlight scenarios justified with a documented performance model, or only by the observed value of ~8.2? [Clarity, Spec §FR-005]
- [ ] CHK012 Does the spec define what constitutes a "genuine regression" vs. acceptable degradation for each autofocus algorithm? [Clarity, Spec §FR-004]
- [ ] CHK013 Is the MEA fourth-order phase error test's dual tolerance (entropy within 1%, PMR within 5 dB) documented as a requirement, or only in the implementation? [Traceability, Gap]

## Test Robustness — Consistency

- [ ] CHK014 Are tolerance values consistent across all four autofocus "does not degrade" tests, and is the rationale for uniform vs. per-algorithm tolerances stated? [Consistency, Spec §FR-004]
- [ ] CHK015 Is the PNR threshold consistent across all scenario tests, or are per-scenario thresholds defined with individual rationale? [Consistency, Spec §FR-005]
- [ ] CHK016 Does SC-002 ("10 consecutive runs with zero failures") define the test environment conditions (same machine, same seed, same configuration)? [Measurability, Spec §SC-002]

## Regression Prevention — Gap Analysis

- [ ] CHK017 Are requirements defined to prevent re-introduction of private-method coupling between pipeline and MoCo algorithms? [Coverage, Gap]
- [ ] CHK018 Is there a requirement that new autofocus algorithms MUST implement `estimate_phase_error()` (not just `focus()`), enforced by the base class or tests? [Coverage, Gap]
- [ ] CHK019 Are requirements specified for new MoCo algorithms to work with the pipeline without modification to `runner.py`? [Coverage, Gap]
- [ ] CHK020 Does the spec address whether the unused `platform_params` fixture removal could affect external test dependencies or downstream consumers? [Assumption, Spec §Assumptions]

## Dependencies & Assumptions

- [ ] CHK021 Is the assumption "first-order MoCo is correct and serves as reference" validated or just stated? [Assumption, Spec §Assumptions]
- [ ] CHK022 Is the assumption that PGA's internal `_estimate_phase_error_from_image()` is correct explicitly validated, given it's being exposed through a new public interface? [Assumption, Spec §Assumptions]
- [ ] CHK023 Are the dependencies between US1 (MoCo fix) and US2-US4 (independent fixes) explicitly documented in the spec, not just the tasks? [Traceability, Gap]

## Notes

- Check items off as completed: `[x]`
- Items marked [Gap] identify requirements that may need to be added to the spec
- Items marked [Ambiguity] identify requirements that need clarification
- Items marked [Assumption] identify claims that should be validated
