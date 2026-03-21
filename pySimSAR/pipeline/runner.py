"""Processing pipeline orchestrator for SAR data.

Chains processing steps in order:
    MoCo → range compression → autofocus → azimuth compression → geocoding → polsar

Each step is optional and driven by ProcessingConfig. The pipeline
operates on RawData and produces SARImage(s) and optional decomposition
results.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from pySimSAR.core.types import PhaseHistoryData, RawData, SARImage, SARMode
from pySimSAR.io.config import ProcessingConfig


@dataclass
class PipelineResult:
    """Container for processing pipeline output.

    Attributes
    ----------
    images : dict[str, SARImage]
        Formed images keyed by channel name.
    phase_history : dict[str, PhaseHistoryData]
        Range-compressed phase history per channel (intermediate result).
    raw_data_ref : dict[str, RawData] | None
        Reference to the raw data used for Doppler spectrum display.
    decomposition : dict[str, np.ndarray] | None
        Polarimetric decomposition results, if computed.
    steps_applied : list[str]
        Names of processing steps that were applied, in order.
    """

    images: dict[str, SARImage] = field(default_factory=dict)
    phase_history: dict[str, PhaseHistoryData] = field(default_factory=dict)
    raw_data_ref: dict[str, RawData] | None = None
    decomposition: dict[str, np.ndarray] | None = None
    steps_applied: list[str] = field(default_factory=list)


class PipelineRunner:
    """Sequential SAR processing pipeline driven by ProcessingConfig.

    Parameters
    ----------
    config : ProcessingConfig
        Algorithm selection and parameters for each processing step.
    """

    def __init__(
        self,
        config: ProcessingConfig,
        stage_callback: Callable[[str], object] | None = None,
    ) -> None:
        if config is None:
            raise ValueError("config must not be None")
        self._config = config
        self._stage_cb = stage_callback or (lambda _msg: None)

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
        result.raw_data_ref = raw_data

        # Validate configuration against raw data
        self.validate_config(raw_data)

        # Step 1: Motion Compensation (optional)
        if self._config.moco is not None:
            self._stage_cb(f"Motion compensation ({self._config.moco})")
            from pySimSAR.algorithms.moco import moco_registry

            moco_cls = moco_registry.get(self._config.moco)
            moco_alg = moco_cls(**self._config.moco_params)

            # nav_data may be a list of NavigationData from multiple sensors;
            # MoCo expects a single NavigationData with position measurements.
            moco_nav = nav_data
            if isinstance(nav_data, list):
                moco_nav = None
                for nd in nav_data:
                    if getattr(nd, "position", None) is not None:
                        moco_nav = nd
                        break
                if moco_nav is None:
                    raise ValueError(
                        "Motion compensation requires GPS sensor data "
                        "(enable GPS under Platform settings)"
                    )

            # MoCo fits its own straight-line reference from GPS data —
            # no "ideal" trajectory is passed.
            for ch, rd in raw_data.items():
                raw_data[ch] = moco_alg.compensate(rd, moco_nav)
            result.steps_applied.append(f"moco:{self._config.moco}")

            # After MoCo, echo phases are consistent with the fitted
            # straight-line reference. Build a matching Trajectory for
            # downstream image formation.
            from pySimSAR.motion.trajectory import Trajectory as _Traj
            first_rd = raw_data[next(iter(raw_data))]
            nav_pos = moco_alg._align_nav_positions(
                first_rd.echo.shape[0], first_rd.prf, moco_nav,
            )
            smoothed_pos = moco_alg._smooth_positions(nav_pos)
            fitted_pos = moco_alg._fit_straight_line(smoothed_pos)
            dt = 1.0 / raw_data[next(iter(raw_data))].prf
            fitted_vel = np.gradient(fitted_pos, dt, axis=0)
            trajectory = _Traj(
                time=np.arange(len(fitted_pos)) * dt,
                position=fitted_pos,
                velocity=fitted_vel,
                attitude=np.zeros((len(fitted_pos), 3)),
            )

        # Step 2: Image Formation (required)
        from pySimSAR.algorithms.image_formation import image_formation_registry

        if_cls = image_formation_registry.get(self._config.image_formation)
        if_alg = if_cls(**self._config.image_formation_params)

        if self._config.autofocus is not None:
            # Two-step: range compress → autofocus → azimuth compress
            from pySimSAR.algorithms.autofocus import autofocus_registry

            af_cls = autofocus_registry.get(self._config.autofocus)
            af_alg = af_cls(**self._config.autofocus_params)

            self._stage_cb(
                f"Range compression ({self._config.image_formation})"
            )
            for ch, rd in raw_data.items():
                phd = if_alg.range_compress(rd, radar)
                result.phase_history[ch] = phd
                result.steps_applied.append(f"range_compress:{self._config.image_formation}")

            self._stage_cb(f"Autofocusing ({self._config.autofocus})")
            for ch in list(result.phase_history):
                phd = result.phase_history[ch]

                def _az_compress(phase_history):
                    return if_alg.azimuth_compress(phase_history, radar, trajectory)

                image = af_alg.focus(phd, _az_compress)
                result.images[ch] = image

            result.steps_applied.append(f"autofocus:{self._config.autofocus}")
        else:
            # Direct: full process()
            self._stage_cb(
                f"Image formation ({self._config.image_formation})"
            )
            for ch, rd in raw_data.items():
                image = if_alg.process(rd, radar, trajectory)
                result.images[ch] = image
            result.steps_applied.append(f"image_formation:{self._config.image_formation}")

        # Crop range to remove waveform-duration padding after compression.
        # The receive window includes wf_duration beyond the far range for
        # matched-filter support, but those samples are meaningless after
        # range compression.
        self._crop_range_padding(result.images, raw_data, radar)

        # Step 3: Geocoding (optional)
        if self._config.geocoding is not None:
            self._stage_cb(f"Geocoding ({self._config.geocoding})")
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
            self._stage_cb(
                f"Polarimetric decomposition "
                f"({self._config.polarimetric_decomposition})"
            )
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

    @staticmethod
    def _crop_range_padding(
        images: dict[str, SARImage],
        raw_data: dict[str, RawData],
        radar: object,
    ) -> None:
        """Crop waveform-duration padding from the range dimension.

        The receive window includes extra samples (waveform duration)
        beyond the far range so that matched filtering can process the
        last echo.  After range compression those samples contain only
        compressed sidelobes.  Cropping them produces an image whose
        range extent matches the user-specified swath.
        """

        first_rd = next(iter(raw_data.values()))
        wf_duration = radar.waveform.duration()
        padding_samples = int(wf_duration * first_rd.sample_rate)

        if padding_samples <= 0:
            return

        for ch, img in images.items():
            n_rng = img.data.shape[1]
            keep = max(1, n_rng - padding_samples)
            if keep < n_rng:
                images[ch] = SARImage(
                    data=img.data[:, :keep],
                    pixel_spacing_range=img.pixel_spacing_range,
                    pixel_spacing_azimuth=img.pixel_spacing_azimuth,
                    geometry=img.geometry,
                    algorithm=img.algorithm,
                    channel=img.channel,
                    near_range=img.near_range,
                    geo_transform=img.geo_transform,
                    projection_wkt=img.projection_wkt,
                )


__all__ = ["PipelineRunner", "PipelineResult"]
