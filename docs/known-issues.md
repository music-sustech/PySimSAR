# Known Issues and Limitations

This page documents known bugs, incomplete features, and workarounds in PySimSAR v0.1.

## PGA Autofocus Vertical Streaks

**Severity**: Medium
**Affected scenarios**: Scenes with strong isolated scatterers in spotlight mode when using PGA autofocus with default parameters.

**Description**: The Phase Gradient Autofocus (PGA) algorithm can produce vertical streak artifacts in the focused image under certain conditions. This occurs when the dominant scatterer selection picks targets with insufficient isolation, causing phase gradient estimation errors that manifest as azimuth-direction streaks.

**Workaround**:

- Increase `n_dominant` parameter to use more scatterers for averaging
- Reduce `window_fraction` to narrow the estimation window
- Use Minimum Entropy Autofocus (MEA) as an alternative for affected scenes
- Verify the sharpness guard is active (enabled by default) — it prevents divergence but may not fully eliminate streaks

```python
config = ProcessingConfig(
    image_formation="range_doppler",
    autofocus="pga",
    autofocus_params={
        "n_dominant": 20,          # default: 10
        "window_fraction": 0.3,    # default: 0.5
        "max_iterations": 30,
    },
)
```

---

## Motion Compensation with GPS Noise

**Severity**: Medium
**Affected scenarios**: Simulations combining platform perturbation (Dryden turbulence) with GPS sensor noise, particularly at high turbulence intensities.

**Description**: When both motion perturbation and GPS navigation errors are active, the motion compensation algorithms receive noisy position estimates. The first-order MoCo corrects bulk phase errors adequately, but residual errors from GPS noise can degrade second-order MoCo performance. This is because the current implementation uses GPS positions directly without filtering.

**Workaround**:

- Use first-order MoCo only (skip second-order) when GPS noise is significant
- Reduce GPS error magnitude in the sensor model
- Apply autofocus after MoCo to correct residual phase errors
- A GPS/INS Kalman filter fusion is planned for a future release but not yet implemented

```python
config = ProcessingConfig(
    moco="first_order",       # use first-order only
    image_formation="range_doppler",
    autofocus="pga",          # autofocus corrects residual errors
)
```

---

## Numba Acceleration

**Severity**: Low (performance, not correctness)
**Status**: Deferred to future release

**Description**: The signal simulation engine uses NumPy vectorized operations for echo computation. Numba JIT compilation of the inner pulse loop could provide significant speedup (estimated 5-10x) for large simulations, but this optimization has not yet been implemented.

**Impact**: Large simulations (>1000 pulses with many targets) may be slow. The current implementation is correct but not performance-optimized for production-scale scenarios.

**Workaround**: Reduce simulation size (fewer pulses or targets) for interactive use. Batch processing can be parallelized at the script level by running multiple simulations as separate processes.

---

## ScanSAR Mode

**Severity**: Low
**Status**: Partially implemented

**Description**: The ScanSAR imaging mode (`SARMode.SCANMAR`) is defined in the type system and supported by the `SARModeConfig` dataclass, but the image formation algorithms have not been fully validated for ScanSAR burst-mode processing. Stripmap and spotlight modes are fully tested.

**Workaround**: Use stripmap or spotlight modes for validated results. ScanSAR configuration can be set up but image quality may not be optimal.

---

## Distributed Target Performance

**Severity**: Low
**Status**: Known limitation

**Description**: Distributed targets with fine cell sizes generate a large number of scatterer contributions per pulse. For grids larger than approximately 100x100 cells, simulation time scales quadratically and may become impractical.

**Workaround**: Use coarser cell sizes for large distributed targets, or represent extended scenes as collections of point targets at representative positions.
