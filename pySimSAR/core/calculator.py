"""SAR system calculator — derives system values from input parameters."""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = ["SARCalculator", "CalculatedResult"]


@dataclass
class CalculatedResult:
    value: float
    unit: str
    warning: str | None = None


class SARCalculator:
    """Computes derived SAR system values from input parameters."""

    C = 299792458.0  # speed of light (m/s)
    K_B = 1.380649e-23  # Boltzmann constant (J/K)

    # ------------------------------------------------------------------ public

    def compute(self, params: dict) -> dict[str, CalculatedResult]:
        """Compute all derived values from a parameter dict.

        Expected *params* keys (all SI units):
            carrier_freq, prf, bandwidth, duty_cycle, transmit_power,
            az_beamwidth, el_beamwidth, depression_angle,
            velocity, altitude, noise_figure, system_losses, receiver_gain_dB,
            reference_temp, mode,
            near_range (opt), far_range (opt), flight_time (opt),
            start_position (opt), stop_position (opt).
        """
        keys = [
            "antenna_gain",
            "wavelength",
            "pulse_width",
            "range_resolution",
            "azimuth_resolution",
            "unambiguous_range",
            "unambiguous_doppler",
            "swath_width_ground",
            "nesz",
            "snr_single_look",
            "n_range_samples",
            "synthetic_aperture",
            "doppler_bandwidth",
            "n_pulses",
            "flight_time",
            "track_length",
        ]
        results: dict[str, CalculatedResult] = {}
        for key in keys:
            try:
                results[key] = self.compute_single(key, params)
            except _SkipCalculation:
                pass
        return results

    def compute_single(self, key: str, params: dict) -> CalculatedResult:
        """Compute a single derived value identified by *key*."""
        method = self._DISPATCH.get(key)
        if method is None:
            raise KeyError(f"Unknown derived quantity: {key!r}")
        return method(self, params)

    # --------------------------------------------------------------- helpers

    def _wavelength(self, params: dict) -> float:
        return self.C / params["carrier_freq"]

    def _antenna_length(self, params: dict) -> float:
        return self._wavelength(params) / params["az_beamwidth"]

    def _mid_range(self, params: dict) -> float:
        nr = params.get("near_range")
        fr = params.get("far_range")
        if nr is not None and fr is not None:
            return (nr + fr) / 2.0
        return params["altitude"] / math.sin(params["depression_angle"])

    @staticmethod
    def _db_to_linear(db: float) -> float:
        return 10.0 ** (db / 10.0)

    # -------------------------------------------------------- derived values

    def _calc_antenna_gain(self, params: dict) -> CalculatedResult:
        """G = 4*pi*eta / (theta_az * theta_el), eta=0.6 typical."""
        eta = 0.6
        theta_az = params["az_beamwidth"]
        theta_el = params["el_beamwidth"]
        g_linear = 4.0 * math.pi * eta / (theta_az * theta_el)
        g_dB = 10.0 * math.log10(g_linear)
        return CalculatedResult(value=g_dB, unit="dBi")

    def _calc_wavelength(self, params: dict) -> CalculatedResult:
        return CalculatedResult(value=self._wavelength(params), unit="m")

    def _calc_pulse_width(self, params: dict) -> CalculatedResult:
        val = params["duty_cycle"] / params["prf"]
        return CalculatedResult(value=val, unit="s")

    def _calc_range_resolution(self, params: dict) -> CalculatedResult:
        val = self.C / (2.0 * params["bandwidth"])
        return CalculatedResult(value=val, unit="m")

    def _calc_azimuth_resolution(self, params: dict) -> CalculatedResult:
        antenna_length = self._antenna_length(params)
        mode = params.get("mode", "stripmap")
        if mode == "stripmap":
            val = antenna_length / 2.0
        elif mode == "spotlight":
            # Spotlight can achieve finer resolution; use antenna_length / 2
            # as upper bound — actual value depends on dwell time.
            val = antenna_length / 2.0
        else:
            val = antenna_length / 2.0
        return CalculatedResult(value=val, unit="m")

    def _calc_unambiguous_range(self, params: dict) -> CalculatedResult:
        val = self.C / (2.0 * params["prf"])
        warning = None
        fr = params.get("far_range")
        if fr is not None and val < fr:
            warning = (
                f"Unambiguous range ({val:.1f} m) is less than "
                f"far range ({fr:.1f} m) — range ambiguity risk"
            )
        return CalculatedResult(value=val, unit="m", warning=warning)

    def _calc_unambiguous_doppler(self, params: dict) -> CalculatedResult:
        wl = self._wavelength(params)
        val = wl * params["prf"] / 4.0
        warning = None
        v = params.get("velocity")
        if v is not None and val < v:
            warning = (
                f"Unambiguous Doppler velocity ({val:.1f} m/s) is less than "
                f"platform velocity ({v:.1f} m/s) — Doppler ambiguity risk"
            )
        return CalculatedResult(value=val, unit="m/s", warning=warning)

    def _calc_swath_width_ground(self, params: dict) -> CalculatedResult:
        nr = params.get("near_range")
        fr = params.get("far_range")
        if nr is None or fr is None:
            raise _SkipCalculation
        val = (fr - nr) / math.sin(params["depression_angle"])
        return CalculatedResult(value=val, unit="m")

    def _calc_nesz(self, params: dict) -> CalculatedResult:
        wl = self._wavelength(params)
        R = self._mid_range(params)
        k = self.K_B
        T = params.get("reference_temp", 290.0)
        F = self._db_to_linear(params["noise_figure"])
        B = params["bandwidth"]
        L = self._db_to_linear(params["system_losses"])
        Pt = params["transmit_power"]
        G = self._db_to_linear(self._calc_antenna_gain(params).value)
        prf = params["prf"]
        dc = params["duty_cycle"]

        # Pulse energy related term: c * duty_cycle / (2 * prf) is the range
        # extent illuminated per pulse interval — used as the ground patch
        # normalisation.
        numerator = (4.0 * math.pi) ** 3 * R**4 * k * T * F * B * L
        denominator = Pt * G**2 * wl**2 * (self.C * dc / (2.0 * prf))

        nesz_linear = numerator / denominator
        nesz_dB = 10.0 * math.log10(nesz_linear)

        warning = None
        if nesz_dB > -10.0:
            warning = (
                f"NESZ ({nesz_dB:.1f} dB) is above -10 dB — "
                "system sensitivity may be insufficient"
            )
        return CalculatedResult(value=nesz_dB, unit="dB", warning=warning)

    def _calc_snr_single_look(self, params: dict) -> CalculatedResult:
        wl = self._wavelength(params)
        R = self._mid_range(params)
        k = self.K_B
        T = params.get("reference_temp", 290.0)
        F = self._db_to_linear(params["noise_figure"])
        B = params["bandwidth"]
        L = self._db_to_linear(params["system_losses"])
        Pt = params["transmit_power"]
        G = self._db_to_linear(self._calc_antenna_gain(params).value)
        sigma = 1.0  # 1 m^2 reference target

        numerator = Pt * G**2 * wl**2 * sigma
        denominator = (4.0 * math.pi) ** 3 * R**4 * k * T * F * B * L

        snr_linear = numerator / denominator
        snr_dB = 10.0 * math.log10(snr_linear)

        warning = None
        if snr_dB < 10.0:
            warning = (
                f"Single-look SNR ({snr_dB:.1f} dB) is below 10 dB — "
                "image quality may be degraded"
            )
        return CalculatedResult(value=snr_dB, unit="dB", warning=warning)

    def _calc_n_range_samples(self, params: dict) -> CalculatedResult:
        nr = params.get("near_range")
        fr = params.get("far_range")
        if nr is None or fr is None:
            raise _SkipCalculation
        swath_slant = fr - nr
        sample_rate = params.get("sample_rate", 2.0 * params["bandwidth"])
        val = math.ceil(sample_rate * 2.0 * swath_slant / self.C)
        return CalculatedResult(value=float(val), unit="count")

    def _calc_synthetic_aperture(self, params: dict) -> CalculatedResult:
        wl = self._wavelength(params)
        R = self._mid_range(params)
        antenna_length = self._antenna_length(params)
        val = wl * R / antenna_length
        return CalculatedResult(value=val, unit="m")

    def _calc_doppler_bandwidth(self, params: dict) -> CalculatedResult:
        az_res = self._calc_azimuth_resolution(params).value
        val = 2.0 * params["velocity"] / az_res
        return CalculatedResult(value=val, unit="Hz")

    def _calc_n_pulses(self, params: dict) -> CalculatedResult:
        ft = self._resolve_flight_time(params)
        if ft is None:
            raise _SkipCalculation
        val = params["prf"] * ft
        return CalculatedResult(value=float(math.floor(val)), unit="count")

    def _calc_flight_time(self, params: dict) -> CalculatedResult:
        ft = self._resolve_flight_time(params)
        if ft is None:
            raise _SkipCalculation
        return CalculatedResult(value=ft, unit="s")

    def _calc_track_length(self, params: dict) -> CalculatedResult:
        ft = self._resolve_flight_time(params)
        if ft is None:
            raise _SkipCalculation
        val = params["velocity"] * ft
        return CalculatedResult(value=val, unit="m")

    # --------------------------------------------------------- internal util

    def _resolve_flight_time(self, params: dict) -> float | None:
        """Return flight_time from params or derive from start/stop positions."""
        start = params.get("start_position")
        stop = params.get("stop_position")
        if start is not None and stop is not None:
            dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(start, stop)))
            v = params["velocity"]
            if v > 0:
                return dist / v
        ft = params.get("flight_time")
        return ft

    # ---------------------------------------------------- dispatch table

    _DISPATCH: dict[str, object] = {
        "antenna_gain": _calc_antenna_gain,
        "wavelength": _calc_wavelength,
        "pulse_width": _calc_pulse_width,
        "range_resolution": _calc_range_resolution,
        "azimuth_resolution": _calc_azimuth_resolution,
        "unambiguous_range": _calc_unambiguous_range,
        "unambiguous_doppler": _calc_unambiguous_doppler,
        "swath_width_ground": _calc_swath_width_ground,
        "nesz": _calc_nesz,
        "snr_single_look": _calc_snr_single_look,
        "n_range_samples": _calc_n_range_samples,
        "synthetic_aperture": _calc_synthetic_aperture,
        "doppler_bandwidth": _calc_doppler_bandwidth,
        "n_pulses": _calc_n_pulses,
        "flight_time": _calc_flight_time,
        "track_length": _calc_track_length,
    }


class _SkipCalculation(Exception):
    """Raised internally when a calculation cannot proceed due to missing params."""
