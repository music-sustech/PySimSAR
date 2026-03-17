"""Processing pipeline orchestrator for SAR data.

Chains processing steps in order:
    MoCo → range compression → autofocus → azimuth compression → geocoding → polsar

Each step is optional and driven by ProcessingConfig. The pipeline
operates on RawData and produces SARImage(s) and optional decomposition
results.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from pySimSAR.core.types import RawData, SARImage, SARMode
from pySimSAR.io.config import ProcessingConfig


@dataclass
class PipelineResult:
    """Container for processing pipeline output.

    Attributes
    ----------
    images : dict[str, SARImage]
        Formed images keyed by channel name.
    decomposition : dict[str, np.ndarray] | None
        Polarimetric decomposition results, if computed.
    steps_applied : list[str]
        Names of processing steps that were applied, in order.
    """

    images: dict[str, SARImage] = field(default_factory=dict)
    decomposition: dict[str, np.ndarray] | None = None
    steps_applied: list[str] = field(default_factory=list)


class PipelineRunner:
    """Sequential SAR processing pipeline driven by ProcessingConfig.

    Parameters
    ----------
    config : ProcessingConfig
        Algorithm selection and parameters for each processing step.
    """

    def __init__(self, config: ProcessingConfig) -> None:
        if config is None:
            raise ValueError("config must not be None")
        self._config = config

    @property
    def config(self) -> ProcessingConfig:
        return self._config

    def validate_config(
        self,
        raw_data: dict[str, RawData],
    ) -> None:
        """Validate that the processing config is compatible with the raw data.

        Checks that the selected image formation algorithm supports the SAR
        mode present in the raw data.

        Parameters
        ----------
        raw_data : dict[str, RawData]
            Raw echo data keyed by polarization channel.

        Raises
        ------
        ValueError
            If the image formation algorithm does not support the SAR mode.
        """
        from pySimSAR.algorithms.image_formation import image_formation_registry

        if_cls = image_formation_registry.get(self._config.image_formation)
        if_alg = if_cls(**self._config.image_formation_params)

        # Get the SAR mode from the first channel
        first_rd = next(iter(raw_data.values()))
        data_mode = SARMode(first_rd.sar_mode)

        if data_mode not in if_alg.supported_modes():
            supported_names = [m.value for m in if_alg.supported_modes()]
            raise ValueError(
                f"Image formation algorithm '{self._config.image_formation}' "
                f"does not support SAR mode '{data_mode.value}'. "
                f"Supported modes: {supported_names}"
            )

    def run(
        self,
        raw_data: dict[str, RawData],
        radar: object,
        trajectory: object,
        nav_data: object | None = None,
        ideal_trajectory: object | None = None,
    ) -> PipelineResult:
        """Execute the processing pipeline.

        Parameters
        ----------
        raw_data : dict[str, RawData]
            Raw echo data keyed by polarization channel.
        radar : Radar
            Radar configuration.
        trajectory : Trajectory
            Platform trajectory (true/perturbed).
        nav_data : NavigationData | None
            Navigation sensor data for MoCo.
        ideal_trajectory : Trajectory | None
            Reference (ideal) trajectory for MoCo.

        Returns
        -------
        PipelineResult
            Formed images and optional decomposition.
        """
        result = PipelineResult()

        # Validate configuration against raw data
        self.validate_config(raw_data)

        # Step 1: Motion Compensation (optional)
        if self._config.moco is not None:
            from pySimSAR.algorithms.moco import moco_registry

            moco_cls = moco_registry.get(self._config.moco)
            moco_alg = moco_cls(**self._config.moco_params)

            ref_track = ideal_trajectory if ideal_trajectory is not None else trajectory
            for ch, rd in raw_data.items():
                raw_data[ch] = moco_alg.compensate(rd, nav_data, ref_track)
            result.steps_applied.append(f"moco:{self._config.moco}")

        # Step 2: Image Formation (required)
        from pySimSAR.algorithms.image_formation import image_formation_registry

        if_cls = image_formation_registry.get(self._config.image_formation)
        if_alg = if_cls(**self._config.image_formation_params)

        if self._config.autofocus is not None:
            # Two-step: range compress → autofocus → azimuth compress
            from pySimSAR.algorithms.autofocus import autofocus_registry

            af_cls = autofocus_registry.get(self._config.autofocus)
            af_alg = af_cls(**self._config.autofocus_params)

            for ch, rd in raw_data.items():
                phd = if_alg.range_compress(rd, radar)
                result.steps_applied.append(f"range_compress:{self._config.image_formation}")

                def _az_compress(phase_history):
                    return if_alg.azimuth_compress(phase_history, radar, trajectory)

                image = af_alg.focus(phd, _az_compress)
                result.images[ch] = image

            result.steps_applied.append(f"autofocus:{self._config.autofocus}")
        else:
            # Direct: full process()
            for ch, rd in raw_data.items():
                image = if_alg.process(rd, radar, trajectory)
                result.images[ch] = image
            result.steps_applied.append(f"image_formation:{self._config.image_formation}")

        # Step 3: Geocoding (optional)
        if self._config.geocoding is not None:
            from pySimSAR.algorithms.geocoding import geocoding_registry

            geo_cls = geocoding_registry.get(self._config.geocoding)
            geo_alg = geo_cls(**self._config.geocoding_params)

            for ch in result.images:
                result.images[ch] = geo_alg.transform(
                    result.images[ch], radar, trajectory
                )
            result.steps_applied.append(f"geocoding:{self._config.geocoding}")

        # Step 4: Polarimetric Decomposition (optional)
        if self._config.polarimetric_decomposition is not None:
            from pySimSAR.algorithms.polarimetry import polarimetry_registry

            pol_cls = polarimetry_registry.get(
                self._config.polarimetric_decomposition
            )
            pol_alg = pol_cls(**self._config.polarimetric_decomposition_params)

            # Requires quad-pol data
            required = {"hh", "hv", "vh", "vv"}
            available = set(result.images.keys())
            missing = required - available
            if missing:
                raise ValueError(
                    f"Polarimetric decomposition "
                    f"'{self._config.polarimetric_decomposition}' requires "
                    f"quad-pol channels {sorted(required)}, but channels "
                    f"{sorted(missing)} are missing. Available: "
                    f"{sorted(available)}"
                )

            result.decomposition = pol_alg.decompose(
                result.images["hh"],
                result.images["hv"],
                result.images["vh"],
                result.images["vv"],
            )
            result.steps_applied.append(
                f"polarimetry:{self._config.polarimetric_decomposition}"
            )

        return result


__all__ = ["PipelineRunner", "PipelineResult"]
