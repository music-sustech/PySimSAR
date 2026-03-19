"""Phase history (range-compressed waterfall) visualization panel."""
from __future__ import annotations
import numpy as np
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QComboBox, QHBoxLayout, QLabel
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

class PhaseHistoryPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Controls
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Dynamic Range:"))
        self._dr_combo = QComboBox()
        self._dr_combo.addItems(["40 dB", "60 dB", "80 dB"])
        self._dr_combo.setCurrentText("60 dB")
        ctrl.addWidget(self._dr_combo)
        ctrl.addWidget(QLabel("Colormap:"))
        self._cmap_combo = QComboBox()
        self._cmap_combo.addItems(["viridis", "jet", "gray", "inferno", "hot"])
        ctrl.addWidget(self._cmap_combo)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self._fig = Figure(figsize=(5, 4), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._ax = self._fig.add_subplot(111)
        self._ax.set_title("Phase History")
        self._ax.text(0.5, 0.5, "No data", transform=self._ax.transAxes, ha='center', va='center', fontsize=14, color='gray')
        layout.addWidget(self._canvas)

        self._dr_combo.currentTextChanged.connect(self._refresh)
        self._cmap_combo.currentTextChanged.connect(self._refresh)
        self._data = None

    def update(self, phd):
        """Update with PhaseHistoryData object (has .data attribute, 2D complex array)."""
        self._data = phd
        self._refresh()

    def _refresh(self):
        self._ax.clear()
        if self._data is None:
            self._ax.text(0.5, 0.5, "No data", transform=self._ax.transAxes, ha='center', va='center', fontsize=14, color='gray')
            self._canvas.draw_idle()
            return
        data = np.abs(self._data.data)
        data_db = 20 * np.log10(data + 1e-30)
        peak = data_db.max()
        dr = float(self._dr_combo.currentText().split()[0])
        cmap = self._cmap_combo.currentText()
        self._ax.imshow(data_db.T, aspect='auto', cmap=cmap, vmin=peak - dr, vmax=peak, origin='lower')
        self._ax.set_xlabel("Range")
        self._ax.set_ylabel("Azimuth")
        self._ax.set_title("Phase History (dB)")
        self._canvas.draw_idle()

    def clear(self):
        self._data = None
        self._ax.clear()
        self._ax.text(0.5, 0.5, "No data", transform=self._ax.transAxes, ha='center', va='center', fontsize=14, color='gray')
        self._canvas.draw_idle()
