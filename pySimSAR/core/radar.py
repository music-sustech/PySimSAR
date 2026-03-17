"""Antenna pattern and radar system models."""

from __future__ import annotations

import math
import warnings
from collections.abc import Callable

import numpy as np

from pySimSAR.core.types import LookSide, PolarizationMode, SARMode
from pySimSAR.waveforms.base import Waveform

# Physical constants
C_LIGHT = 299792458.0  # Speed of light (m/s)
K_BOLTZMANN = 1.380649e-23  # Boltzmann constant (J/K)


class AntennaPattern:
    """2D antenna gain pattern with interpolation support.

    The pattern can be specified either as a 2D numpy array of gain values
    (dB) sampled on a regular grid, or as a callable that computes gain
    for arbitrary azimuth/elevation angles.

    Parameters
    ----------
    pattern_2d : np.ndarray | Callable
        2D gain pattern in dB with shape (n_el, n_az), or a callable
        with signature ``(az, el) -> gain_dB``.
    az_beamwidth : float
        3 dB azimuth beamwidth in radians (must be > 0).
    el_beamwidth : float
        3 dB elevation beamwidth in radians (must be > 0).
    az_angles : np.ndarray | None
        Azimuth angle samples in radians. Required when *pattern_2d*
        is an array.
    el_angles : np.ndarray | None
        Elevation angle samples in radians. Required when *pattern_2d*
        is an array.
    peak_gain_dB : float
        Peak antenna gain in dB.
    """

    def __init__(
        self,
        pattern_2d: np.ndarray | Callable[..., float],
        az_beamwidth: float,
        el_beamwidth: float,
        peak_gain_dB: float,
        az_angles: np.ndarray | None = None,
        el_angles: np.ndarray | None = None,
    ) -> None:
        if az_beamwidth <= 0:
            raise ValueError(f"az_beamwidth must be positive, got {az_beamwidth}")
        if el_beamwidth <= 0:
            raise ValueError(f"el_beamwidth must be positive, got {el_beamwidth}")

        self.pattern_2d = pattern_2d
        self.az_beamwidth = az_beamwidth
        self.el_beamwidth = el_beamwidth
        self.peak_gain_dB = peak_gain_dB
        self.az_angles = az_angles
        self.el_angles = el_angles

        # Build interpolator for array patterns
        self._interpolator: Callable[..., float] | None = None
        if isinstance(pattern_2d, np.ndarray):
            if az_angles is None or el_angles is None:
                raise ValueError(
                    "az_angles and el_angles are required when pattern_2d "
                    "is an array"
                )
            if pattern_2d.shape != (len(el_angles), len(az_angles)):
                raise ValueError(
                    f"pattern_2d shape {pattern_2d.shape} does not match "
                    f"(n_el={len(el_angles)}, n_az={len(az_angles)})"
                )
            from scipy.interpolate import RegularGridInterpolator

            self._interpolator = RegularGridInterpolator(
                (el_angles, az_angles),
                pattern_2d,
                method="linear",
                bounds_error=False,
                fill_value=float(np.min(pattern_2d)),
            )

    def gain(self, az: float, el: float) -> float:
        """Evaluate antenna gain at the given angles.

        Parameters
        ----------
        az : float
            Azimuth angle in radians.
        el : float
            Elevation angle in radians.

        Returns
        -------
        float
            Antenna gain in dB.
        """
        if callable(self.pattern_2d) and not isinstance(self.pattern_2d, np.ndarray):
            return float(self.pattern_2d(az, el))

        if self._interpolator is not None:
            return float(self._interpolator((el, az)))

        raise RuntimeError("No valid pattern or interpolator available")


def _coerce_enum(value: str | object, enum_cls: type) -> object:
    """Convert a string to the given enum, passing through existing members."""
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        return enum_cls(value.lower())
    raise TypeError(f"Expected {enum_cls.__name__} or str, got {type(value).__name__}")


class Radar:
    """Radar system model combining waveform, antenna, and operating parameters.

    Parameters
    ----------
    carrier_freq : float
        Carrier frequency in Hz (must be > 0).
    prf : float
        Pulse repetition frequency in Hz (must be > 0).
    transmit_power : float
        Transmit power in Watts (must be > 0).
    waveform : Waveform
        Radar waveform (must not be None).
    antenna : AntennaPattern
        Antenna pattern (must not be None).
    polarization : PolarizationMode | str
        Polarization mode.
    mode : SARMode | str
        SAR imaging mode.
    look_side : LookSide | str
        Radar look direction.
    depression_angle : float
        Depression angle in radians [0, pi/2].
    noise_figure : float
        Noise figure in dB (>= 0, default 3.0).
    system_losses : float
        System losses in dB (>= 0, default 2.0).
    reference_temp : float
        Reference temperature in Kelvin (> 0, default 290.0).
    squint_angle : float
        Squint angle in radians [-pi/2, pi/2] (default 0.0).
    """

    def __init__(
        self,
        carrier_freq: float,
        prf: float,
        transmit_power: float,
        waveform: Waveform,
        antenna: AntennaPattern,
        polarization: PolarizationMode | str,
        mode: SARMode | str,
        look_side: LookSide | str,
        depression_angle: float,
        noise_figure: float = 3.0,
        system_losses: float = 2.0,
        reference_temp: float = 290.0,
        squint_angle: float = 0.0,
        receiver_gain_dB: float = 0.0,
    ) -> None:
        # Validate scalars
        if carrier_freq <= 0:
            raise ValueError(f"carrier_freq must be positive, got {carrier_freq}")
        if prf <= 0:
            raise ValueError(f"prf must be positive, got {prf}")
        if transmit_power <= 0:
            raise ValueError(f"transmit_power must be positive, got {transmit_power}")
        if noise_figure < 0:
            raise ValueError(f"noise_figure must be >= 0, got {noise_figure}")
        if system_losses < 0:
            raise ValueError(f"system_losses must be >= 0, got {system_losses}")
        if reference_temp <= 0:
            raise ValueError(f"reference_temp must be positive, got {reference_temp}")
        if receiver_gain_dB < 0:
            raise ValueError(f"receiver_gain_dB must be >= 0, got {receiver_gain_dB}")
        if not 0 <= depression_angle <= math.pi / 2:
            raise ValueError(
                f"depression_angle must be in [0, pi/2], got {depression_angle}"
            )
        if not -math.pi / 2 <= squint_angle <= math.pi / 2:
            raise ValueError(
                f"squint_angle must be in [-pi/2, pi/2], got {squint_angle}"
            )

        # Validate references
        if waveform is None:
            raise ValueError("waveform must not be None")
        if antenna is None:
            raise ValueError("antenna must not be None")

        self.carrier_freq = carrier_freq
        self.prf = prf
        self.transmit_power = transmit_power
        self.noise_figure = noise_figure
        self.system_losses = system_losses
        self.reference_temp = reference_temp
        self.receiver_gain = receiver_gain_dB
        self.waveform = waveform
        self.antenna = antenna
        self.depression_angle = depression_angle
        self.squint_angle = squint_angle

        # Coerce string values to enums
        self.polarization = _coerce_enum(polarization, PolarizationMode)
        self.mode = _coerce_enum(mode, SARMode)
        self.look_side = _coerce_enum(look_side, LookSide)

        # Warn if waveform duration exceeds PRI
        if waveform.duration(prf) > 1.0 / prf:
            warnings.warn(
                f"Waveform duration ({waveform.duration(prf):.6e} s) exceeds "
                f"PRI ({1.0 / prf:.6e} s). Duty cycle may be too high.",
                stacklevel=2,
            )

    @property
    def bandwidth(self) -> float:
        """Waveform bandwidth in Hz."""
        return self.waveform.bandwidth

    @property
    def pri(self) -> float:
        """Pulse repetition interval in seconds."""
        return 1.0 / self.prf

    @property
    def wavelength(self) -> float:
        """Radar wavelength in meters."""
        return C_LIGHT / self.carrier_freq

    @property
    def total_noise_figure(self) -> float:
        """Total system noise figure in dB (cascade: passive loss + receiver)."""
        l_sys = 10.0 ** (self.system_losses / 10.0)
        f_rx = 10.0 ** (self.noise_figure / 10.0)
        f_total = l_sys * f_rx
        return 10.0 * np.log10(f_total)

    @property
    def noise_power(self) -> float:
        """Thermal noise power at receiver output in Watts."""
        f_total_linear = 10.0 ** (self.total_noise_figure / 10.0)
        g_rx_linear = 10.0 ** (self.receiver_gain / 10.0)
        return K_BOLTZMANN * self.reference_temp * self.bandwidth * f_total_linear * g_rx_linear


def create_antenna_from_preset(
    preset: str,
    az_beamwidth: float,
    el_beamwidth: float,
    peak_gain_dB: float,
) -> AntennaPattern:
    """Create an AntennaPattern from a named preset.

    Parameters
    ----------
    preset : str
        Preset name: "flat", "sinc", or "gaussian".
    az_beamwidth : float
        3 dB azimuth beamwidth in radians.
    el_beamwidth : float
        3 dB elevation beamwidth in radians.
    peak_gain_dB : float
        Peak antenna gain in dB.

    Returns
    -------
    AntennaPattern
        Configured antenna pattern.
    """
    preset = preset.lower()
    floor_dB = -60.0

    if preset == "flat":
        half_az = az_beamwidth / 2.0
        half_el = el_beamwidth / 2.0

        def flat_pattern(az: float, el: float) -> float:
            if abs(az) < half_az and abs(el) < half_el:
                return peak_gain_dB
            return peak_gain_dB + floor_dB

        return AntennaPattern(
            pattern_2d=flat_pattern,
            az_beamwidth=az_beamwidth,
            el_beamwidth=el_beamwidth,
            peak_gain_dB=peak_gain_dB,
        )

    elif preset == "sinc":
        def sinc_pattern(az: float, el: float) -> float:
            az_arg = 0.886 * az / az_beamwidth
            el_arg = 0.886 * el / el_beamwidth
            gain_az = np.sinc(az_arg)  # np.sinc includes the pi factor
            gain_el = np.sinc(el_arg)
            gain_dB = 20.0 * np.log10(max(abs(gain_az * gain_el), 1e-30))
            return peak_gain_dB + max(floor_dB, gain_dB)

        return AntennaPattern(
            pattern_2d=sinc_pattern,
            az_beamwidth=az_beamwidth,
            el_beamwidth=el_beamwidth,
            peak_gain_dB=peak_gain_dB,
        )

    elif preset == "gaussian":
        def gaussian_pattern(az: float, el: float) -> float:
            loss = 12.0 * ((az / az_beamwidth) ** 2 + (el / el_beamwidth) ** 2)
            return peak_gain_dB - loss

        return AntennaPattern(
            pattern_2d=gaussian_pattern,
            az_beamwidth=az_beamwidth,
            el_beamwidth=el_beamwidth,
            peak_gain_dB=peak_gain_dB,
        )

    else:
        raise ValueError(f"Unknown antenna preset: {preset!r}. Use 'flat', 'sinc', or 'gaussian'.")


__all__ = ["AntennaPattern", "Radar", "C_LIGHT", "K_BOLTZMANN", "create_antenna_from_preset"]
