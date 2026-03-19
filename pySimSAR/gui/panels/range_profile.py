"""Range profile (1D power vs range) visualization panel."""
from __future__ import annotations
import numpy as np
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QHBoxLayout, QLabel, QSpinBox, QCheckBox
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

class RangeProfilePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Azimuth Line:"))
        self._az_spin = QSpinBox()
        self._az_spin.setRange(0, 0)
        ctrl.addWidget(self._az_spin)
        self._avg_check = QCheckBox("Average All")
        ctrl.addWidget(self._avg_check)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self._fig = Figure(figsize=(5, 3), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._ax = self._fig.add_subplot(111)
        self._ax.text(0.5, 0.5, "No data", transform=self._ax.transAxes, ha='center', va='center', fontsize=14, color='gray')
        layout.addWidget(self._canvas)

        self._image = None
        self._az_spin.valueChanged.connect(self._refresh)
        self._avg_check.toggled.connect(self._refresh)

    def update(self, image):
        """Update with SARImage (has .data attribute)."""
        self._image = image
        self._az_spin.setRange(0, max(0, image.data.shape[1] - 1))
        self._refresh()

    def _refresh(self):
        self._ax.clear()
        if self._image is None:
            self._ax.text(0.5, 0.5, "No data", transform=self._ax.transAxes, ha='center', va='center', fontsize=14, color='gray')
            self._canvas.draw_idle()
            return
        data = self._image.data
        if self._avg_check.isChecked():
            profile = np.mean(np.abs(data) ** 2, axis=1)
        else:
            az = self._az_spin.value()
            profile = np.abs(data[:, az]) ** 2
        profile_db = 10 * np.log10(profile + 1e-30)
        self._ax.plot(profile_db)
        self._ax.set_xlabel("Range Bin")
        self._ax.set_ylabel("Power (dB)")
        self._ax.set_title("Range Profile")
        self._ax.grid(True, alpha=0.3)
        self._canvas.draw_idle()

    def clear(self):
        self._image = None
        self._ax.clear()
        self._ax.text(0.5, 0.5, "No data", transform=self._ax.transAxes, ha='center', va='center', fontsize=14, color='gray')
        self._canvas.draw_idle()
