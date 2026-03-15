"""Waveform and phase noise model registries."""

from pySimSAR.algorithms.registry import AlgorithmRegistry
from pySimSAR.waveforms.base import Waveform
from pySimSAR.waveforms.phase_noise import PhaseNoiseModel

waveform_registry = AlgorithmRegistry(Waveform, "waveform")
phase_noise_registry = AlgorithmRegistry(PhaseNoiseModel, "phase_noise")

__all__ = ["waveform_registry", "phase_noise_registry"]
