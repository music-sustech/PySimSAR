"""Waveform and phase noise model implementations."""

# Import concrete implementations to trigger registry registration.
from pySimSAR.waveforms.fmcw import FMCWWaveform  # noqa: F401
from pySimSAR.waveforms.lfm import LFMWaveform  # noqa: F401
from pySimSAR.waveforms.phase_noise import CompositePSDPhaseNoise  # noqa: F401
from pySimSAR.waveforms.registry import phase_noise_registry

phase_noise_registry.register(CompositePSDPhaseNoise)

__all__ = ["LFMWaveform", "FMCWWaveform", "CompositePSDPhaseNoise"]
