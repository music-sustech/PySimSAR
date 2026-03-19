# Contract: Calculated Values Panel

## Interface

The calculated values panel is a read-only display in the bottom-right of the main window. It subscribes to parameter changes and recomputes derived quantities.

### SARCalculator (Library Layer)

```python
class SARCalculator:
    """Computes derived SAR system values from input parameters.

    This class lives in pySimSAR/core/ (not GUI) per Constitution II (Library-First).
    """

    def compute(self, params: dict) -> dict[str, CalculatedResult]:
        """Compute all derived values from parameter dict.

        Returns dict keyed by value name, each containing:
        - value: float
        - unit: str
        - warning: str | None (if problematic)
        """

    def compute_single(self, key: str, params: dict) -> CalculatedResult:
        """Compute a single derived value."""
```

### Calculated Values (minimum set per SC-003)

| Key | Name | Formula | Unit | Warning Condition |
|-----|------|---------|------|-------------------|
| wavelength | Wavelength | c / f_c | m | - |
| pulse_width | Pulse Width | duty_cycle / PRF | s | - |
| range_resolution | Range Resolution | c / (2B) | m | - |
| azimuth_resolution | Azimuth Resolution | D/2 (stripmap) | m | - |
| unambiguous_range | Unambiguous Range | c / (2 PRF) | m | < far_range |
| unambiguous_doppler | Unamb. Doppler Vel. | lambda PRF / 4 | m/s | < platform velocity |
| swath_width_ground | Swath Width (ground) | (R_far - R_near) / sin(theta) | m | - |
| nesz | NESZ | (thermal noise eq.) | dB | > -10 dB |
| snr_single_look | Single-Look SNR | (radar equation) | dB | < 10 dB |
| n_range_samples | Range Samples | ceil(2B * delta_R / c * Fs) | count | - |
| synthetic_aperture | Synth. Aperture Length | lambda R / D | m | - |
| doppler_bandwidth | Doppler Bandwidth | 2v / az_res | Hz | - |
| n_pulses | Number of Pulses | PRF * flight_time | count | - |
| flight_time | Flight Time | distance / velocity | s | - |
| track_length | Track Length | velocity * flight_time | m | - |

### GUI Panel Contract

- **Update trigger**: Any `parameter_changed` signal from the tree.
- **Update latency**: < 200 ms (per FR-005).
- **Display format**: Name | Value | Unit, with warning icon (yellow/red) for flagged values.
- **Layout**: Scrollable grid or table, grouped by category (Radar, Geometry, Performance, Flight).
