"""Polarimetric decomposition visualization panel."""
from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class PolarimetryPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Display:"))
        self._display_combo = QComboBox()
        self._display_combo.addItems(["RGB Composite", "Component 1", "Component 2", "Component 3"])
        ctrl.addWidget(self._display_combo)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self._fig = Figure(figsize=(5, 4), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._ax = self._fig.add_subplot(111)
        self._ax.text(
            0.5, 0.5, "No data", transform=self._ax.transAxes,
            ha='center', va='center', fontsize=14, color='gray',
        )
        layout.addWidget(self._canvas)

        self._decomposition = None
        self._display_combo.currentTextChanged.connect(self._refresh)

    def update(self, decomposition):
        """Update with decomposition dict from PipelineResult.decomposition.

        Expected keys vary by algorithm, but common pattern:
        - Pauli: 'red', 'green', 'blue' (each 2D arrays)
        - Freeman: 'volume', 'double_bounce', 'surface'
        """
        self._decomposition = decomposition
        self._refresh()

    def _refresh(self):
        self._ax.clear()
        if self._decomposition is None:
            self._ax.text(
            0.5, 0.5, "No data", transform=self._ax.transAxes,
            ha='center', va='center', fontsize=14, color='gray',
        )
            self._canvas.draw_idle()
            return

        display = self._display_combo.currentText()
        keys = list(self._decomposition.keys())

        if display == "RGB Composite" and len(keys) >= 3:
            r = np.abs(self._decomposition[keys[0]])
            g = np.abs(self._decomposition[keys[1]])
            b = np.abs(self._decomposition[keys[2]])
            # Normalize each channel
            for arr in [r, g, b]:
                mx = arr.max()
                if mx > 0:
                    arr /= mx
            rgb = np.stack([r, g, b], axis=-1)
            self._ax.imshow(rgb, origin='lower', aspect='auto')
            self._ax.set_title(f"RGB: {keys[0]}/{keys[1]}/{keys[2]}")
        else:
            idx = max(0, min(int(display.split()[-1]) - 1, len(keys) - 1)) if "Component" in display else 0
            if idx < len(keys):
                data = np.abs(self._decomposition[keys[idx]])
                data_db = 10 * np.log10(data + 1e-30)
                self._ax.imshow(data_db, origin='lower', aspect='auto', cmap='viridis')
                self._ax.set_title(keys[idx])

        self._canvas.draw_idle()

    def clear(self):
        self._decomposition = None
        self._ax.clear()
        self._ax.text(
            0.5, 0.5, "No data", transform=self._ax.transAxes,
            ha='center', va='center', fontsize=14, color='gray',
        )
        self._canvas.draw_idle()
