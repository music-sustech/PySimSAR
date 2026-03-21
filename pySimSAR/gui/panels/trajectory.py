"""Trajectory viewer panel — 2D deviation plots for ideal vs perturbed flight paths."""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from pySimSAR.motion.trajectory import Trajectory

_AXIS_LABELS = ("East (cross-track)", "North (along-track)", "Up (altitude)")
_AXIS_COLORS = ("#e6194b", "#3cb44b", "#4363d8")  # red, green, blue


class TrajectoryViewerPanel(QWidget):
    """2D trajectory viewer showing deviation between ideal and perturbed paths.

    Displays three subplots (East, North, Up) of position deviation vs time.
    When only one trajectory is available, it shows the absolute position.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._figure = Figure(tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)

        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas, stretch=1)

        self._axes_list = []
        self._setup_axes()

    def _setup_axes(self) -> None:
        self._figure.clear()
        self._axes_list = []
        for i in range(3):
            ax = self._figure.add_subplot(3, 1, i + 1)
            ax.set_ylabel(f"{_AXIS_LABELS[i]}\ndeviation (m)", fontsize=8)
            ax.tick_params(labelsize=7)
            ax.grid(True, alpha=0.3)
            if i < 2:
                ax.tick_params(labelbottom=False)
            self._axes_list.append(ax)
        self._axes_list[-1].set_xlabel("Time (s)", fontsize=8)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_trajectories(
        self,
        ideal: Trajectory | None,
        perturbed: Trajectory | None,
    ) -> None:
        """Update the displayed trajectories.

        If both are provided, plots deviation (perturbed - ideal).
        If only one is provided, plots absolute position.
        """
        self._setup_axes()

        if ideal is None and perturbed is None:
            self._canvas.draw_idle()
            return

        has_both = ideal is not None and perturbed is not None

        if has_both:
            time = ideal.time
            deviation = perturbed.position - ideal.position
            for i, ax in enumerate(self._axes_list):
                ax.plot(time, deviation[:, i], color=_AXIS_COLORS[i], linewidth=1)
                ax.axhline(0, color='gray', linewidth=0.5, linestyle='--')
                rms = float(np.sqrt(np.mean(deviation[:, i] ** 2)))
                ax.set_ylabel(
                    f"{_AXIS_LABELS[i]}\ndeviation (m)\nRMS: {rms:.4f}",
                    fontsize=8,
                )
            self._figure.suptitle(
                "Trajectory Deviation (Perturbed \u2212 Ideal)", fontsize=10
            )
        else:
            traj = ideal if ideal is not None else perturbed
            label = "Ideal" if ideal is not None else "Perturbed"
            time = traj.time
            for i, ax in enumerate(self._axes_list):
                ax.plot(time, traj.position[:, i], color=_AXIS_COLORS[i], linewidth=1)
                ax.set_ylabel(f"{_AXIS_LABELS[i]}\nposition (m)", fontsize=8)
            self._figure.suptitle(f"{label} Trajectory", fontsize=10)

        self._canvas.draw_idle()

    def clear(self) -> None:
        """Remove all plots."""
        self._setup_axes()
        self._canvas.draw_idle()


__all__ = ["TrajectoryViewerPanel"]
