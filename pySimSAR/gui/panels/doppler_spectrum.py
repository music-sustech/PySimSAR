"""Doppler spectrum visualization panel."""
from __future__ import annotations
import numpy as np
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QHBoxLayout, QLabel, QSpinBox, QComboBox
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

class DopplerSpectrumPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Range Bin:"))
        self._rg_spin = QSpinBox()
        self._rg_spin.setRange(0, 0)
        ctrl.addWidget(self._rg_spin)
        ctrl.addWidget(QLabel("Window:"))
        self._win_combo = QComboBox()
        self._win_combo.addItems(["(None)", "hamming", "hanning", "blackman"])
        ctrl.addWidget(self._win_combo)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self._fig = Figure(figsize=(5, 3), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._ax = self._fig.add_subplot(111)
        self._ax.text(0.5, 0.5, "No data", transform=self._ax.transAxes, ha='center', va='center', fontsize=14, color='gray')
        layout.addWidget(self._canvas)

        self._raw_data = None
        self._radar = None
        self._rg_spin.valueChanged.connect(self._refresh)
        self._win_combo.currentTextChanged.connect(self._refresh)

    def update(self, raw_data, radar=None):
        """Update with RawData object and optional Radar for frequency axis."""
        self._raw_data = raw_data
        self._radar = radar
        self._rg_spin.setRange(0, max(0, raw_data.echo.shape[0] - 1))
        self._refresh()

    def _refresh(self):
        self._ax.clear()
        if self._raw_data is None:
            self._ax.text(0.5, 0.5, "No data", transform=self._ax.transAxes, ha='center', va='center', fontsize=14, color='gray')
            self._canvas.draw_idle()
            return
        rg = self._rg_spin.value()
        signal = self._raw_data.echo[rg, :]
        win_name = self._win_combo.currentText()
        if win_name != "(None)":
            win_func = getattr(np, win_name, None)
            if win_func is not None:
                signal = signal * win_func(len(signal))
        spectrum = np.fft.fftshift(np.fft.fft(signal))
        spectrum_db = 20 * np.log10(np.abs(spectrum) + 1e-30)
        n = len(spectrum_db)
        if self._raw_data.prf > 0:
            freqs = np.fft.fftshift(np.fft.fftfreq(n, 1.0 / self._raw_data.prf))
            self._ax.plot(freqs, spectrum_db)
            self._ax.set_xlabel("Doppler Frequency (Hz)")
        else:
            self._ax.plot(spectrum_db)
            self._ax.set_xlabel("Frequency Bin")
        self._ax.set_ylabel("Power (dB)")
        self._ax.set_title("Doppler Spectrum")
        self._ax.grid(True, alpha=0.3)
        self._canvas.draw_idle()

    def clear(self):
        self._raw_data = None
        self._radar = None
        self._ax.clear()
        self._ax.text(0.5, 0.5, "No data", transform=self._ax.transAxes, ha='center', va='center', fontsize=14, color='gray')
        self._canvas.draw_idle()
