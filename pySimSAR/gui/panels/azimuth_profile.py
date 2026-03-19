"""Azimuth profile (1D power vs azimuth) visualization panel."""
from __future__ import annotations
import numpy as np
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QHBoxLayout, QLabel, QSpinBox
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

class AzimuthProfilePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Range Bin:"))
        self._rg_spin = QSpinBox()
        self._rg_spin.setRange(0, 0)
        ctrl.addWidget(self._rg_spin)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self._fig = Figure(figsize=(5, 3), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._ax = self._fig.add_subplot(111)
        self._ax.text(0.5, 0.5, "No data", transform=self._ax.transAxes, ha='center', va='center', fontsize=14, color='gray')
        layout.addWidget(self._canvas)

        self._image = None
        self._rg_spin.valueChanged.connect(self._refresh)

    def update(self, image):
        self._image = image
        self._rg_spin.setRange(0, max(0, image.data.shape[0] - 1))
        self._refresh()

    def _refresh(self):
        self._ax.clear()
        if self._image is None:
            self._ax.text(0.5, 0.5, "No data", transform=self._ax.transAxes, ha='center', va='center', fontsize=14, color='gray')
            self._canvas.draw_idle()
            return
        rg = self._rg_spin.value()
        profile = np.abs(self._image.data[rg, :]) ** 2
        profile_db = 10 * np.log10(profile + 1e-30)
        self._ax.plot(profile_db)
        self._ax.set_xlabel("Azimuth Bin")
        self._ax.set_ylabel("Power (dB)")
        self._ax.set_title("Azimuth Profile")
        self._ax.grid(True, alpha=0.3)
        self._canvas.draw_idle()

    def clear(self):
        self._image = None
        self._ax.clear()
        self._ax.text(0.5, 0.5, "No data", transform=self._ax.transAxes, ha='center', va='center', fontsize=14, color='gray')
        self._canvas.draw_idle()
