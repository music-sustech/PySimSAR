"""Beam animation panel showing radar beam footprint sweeping along the flight path."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph.opengl as gl
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QSlider,
    QLabel,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from pySimSAR.core.radar import Radar


class BeamAnimationPanel(QWidget):
    """3D animation of the radar beam footprint along the flight trajectory.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # State
        self._positions: np.ndarray | None = None
        self._depression_angle: float = 0.0
        self._look_side: str = "right"
        self._current_index: int = 0
        self._playing: bool = False

        # 3D view
        self._view = gl.GLViewWidget()
        self._view.setBackgroundColor("k")

        # Plot items (created on setup)
        self._trajectory_line: gl.GLLinePlotItem | None = None
        self._platform_scatter: gl.GLScatterPlotItem | None = None
        self._beam_line: gl.GLLinePlotItem | None = None

        # Animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self._timer.setInterval(50)  # 20 fps default

        # Controls
        self._play_btn = QPushButton("Play")
        self._play_btn.setFixedWidth(80)
        self._play_btn.clicked.connect(self._toggle_play)

        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setFixedWidth(80)
        self._reset_btn.clicked.connect(self.reset)

        self._speed_label = QLabel("Speed:")
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setMinimum(1)
        self._speed_slider.setMaximum(100)
        self._speed_slider.setValue(20)
        self._speed_slider.valueChanged.connect(self._on_speed_changed)

        # Layout
        toolbar = QHBoxLayout()
        toolbar.addWidget(self._play_btn)
        toolbar.addWidget(self._reset_btn)
        toolbar.addWidget(self._speed_label)
        toolbar.addWidget(self._speed_slider)

        layout = QVBoxLayout(self)
        layout.addWidget(self._view, stretch=1)
        layout.addLayout(toolbar)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setup(self, trajectory, radar: Radar) -> None:
        """Configure the animation with trajectory and radar parameters.

        Parameters
        ----------
        trajectory
            Object with a ``position`` attribute of shape ``(n_pulses, 3)``.
        radar : Radar
            Radar object providing ``depression_angle`` (radians) and
            ``look_side`` (``"left"`` or ``"right"``).
        """
        self.clear()

        positions = np.asarray(trajectory.position, dtype=np.float64)
        if positions.ndim != 2 or positions.shape[1] != 3:
            raise ValueError("trajectory.position must have shape (n, 3)")

        self._positions = positions
        self._depression_angle = float(radar.depression_angle)
        look = radar.look_side
        self._look_side = look.value if hasattr(look, "value") else str(look)
        self._current_index = 0

        # Draw trajectory line
        self._trajectory_line = gl.GLLinePlotItem(
            pos=positions, color=(0.3, 0.8, 1.0, 0.6), width=2, antialias=True
        )
        self._view.addItem(self._trajectory_line)

        # Platform marker (scatter point)
        self._platform_scatter = gl.GLScatterPlotItem(
            pos=positions[:1], color=(1.0, 0.2, 0.2, 1.0), size=10
        )
        self._view.addItem(self._platform_scatter)

        # Beam line from platform to ground intercept
        ground_pt = self._ground_intercept(positions[0])
        beam_pts = np.array([positions[0], ground_pt])
        self._beam_line = gl.GLLinePlotItem(
            pos=beam_pts, color=(1.0, 1.0, 0.0, 0.8), width=2, antialias=True
        )
        self._view.addItem(self._beam_line)

        # Auto-fit camera
        center = positions.mean(axis=0)
        extent = np.ptp(positions, axis=0).max()
        self._view.setCameraPosition(
            distance=extent * 2.0,
            elevation=30,
            azimuth=45,
        )
        self._view.opts["center"] = gl.Vector(center[0], center[1], center[2])  # type: ignore[attr-defined]

    def clear(self) -> None:
        """Remove all items and reset state."""
        self.pause()
        for item in (self._trajectory_line, self._platform_scatter, self._beam_line):
            if item is not None:
                self._view.removeItem(item)
        self._trajectory_line = None
        self._platform_scatter = None
        self._beam_line = None
        self._positions = None
        self._current_index = 0

    def play(self) -> None:
        """Start the animation."""
        if self._positions is None:
            return
        self._playing = True
        self._play_btn.setText("Pause")
        self._timer.start()

    def pause(self) -> None:
        """Pause the animation."""
        self._playing = False
        self._play_btn.setText("Play")
        self._timer.stop()

    def reset(self) -> None:
        """Reset animation to the first frame."""
        self.pause()
        self._current_index = 0
        if self._positions is not None:
            self._update_frame()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _toggle_play(self) -> None:
        if self._playing:
            self.pause()
        else:
            self.play()

    def _on_speed_changed(self, value: int) -> None:
        # Map slider 1..100 to interval 200ms..5ms (slower to faster)
        interval = max(5, int(200 - value * 1.95))
        self._timer.setInterval(interval)

    def _step(self) -> None:
        if self._positions is None:
            self.pause()
            return
        self._current_index += 1
        if self._current_index >= len(self._positions):
            self._current_index = 0  # loop
        self._update_frame()

    def _update_frame(self) -> None:
        pos = self._positions[self._current_index]  # type: ignore[index]
        if self._platform_scatter is not None:
            self._platform_scatter.setData(pos=np.array([pos]))
        if self._beam_line is not None:
            ground_pt = self._ground_intercept(pos)
            self._beam_line.setData(pos=np.array([pos, ground_pt]))

    def _ground_intercept(self, platform_pos: np.ndarray) -> np.ndarray:
        """Compute the ground intercept point of the beam center.

        Uses the depression angle and look side to project from the
        platform position to the ground plane (z=0).
        """
        height = platform_pos[2]
        if height <= 0 or self._depression_angle <= 0:
            # Fallback: directly below
            return np.array([platform_pos[0], platform_pos[1], 0.0])

        # Horizontal offset = height / tan(depression_angle)
        horiz_offset = height / np.tan(self._depression_angle)

        # Determine the across-track direction.  Approximate the flight
        # direction as +x; cross-track is then +/-y depending on look side.
        if self._positions is not None and len(self._positions) > 1:
            idx = self._current_index
            n = len(self._positions)
            # Use neighbouring positions to estimate heading
            i0 = max(0, idx - 1)
            i1 = min(n - 1, idx + 1)
            heading = self._positions[i1] - self._positions[i0]
            heading[2] = 0.0
            norm = np.linalg.norm(heading)
            if norm > 1e-12:
                heading /= norm
            else:
                heading = np.array([1.0, 0.0, 0.0])
        else:
            heading = np.array([1.0, 0.0, 0.0])

        # Cross-track unit vector (perpendicular to heading in xy-plane)
        cross = np.array([-heading[1], heading[0], 0.0])
        if self._look_side == "left":
            cross = -cross

        ground = np.array([
            platform_pos[0] + cross[0] * horiz_offset,
            platform_pos[1] + cross[1] * horiz_offset,
            0.0,
        ])
        return ground
