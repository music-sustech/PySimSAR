"""Algorithm selector widget for the SAR processing pipeline GUI."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFormLayout, QGroupBox

from pySimSAR.algorithms.autofocus import autofocus_registry
from pySimSAR.algorithms.geocoding import geocoding_registry
from pySimSAR.algorithms.image_formation import image_formation_registry
from pySimSAR.algorithms.moco import moco_registry
from pySimSAR.algorithms.polarimetry import polarimetry_registry
from pySimSAR.io.config import ProcessingConfig

_NONE_LABEL = "(None)"


class AlgorithmSelector(QGroupBox):
    """Widget for selecting algorithms in each SAR processing step.

    Populates dropdown choices from the algorithm registries.
    Required steps (image formation) have no None option;
    optional steps include a ``(None)`` entry as the first choice.
    """

    config_changed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__("Algorithm Selection", parent)

        layout = QFormLayout(self)

        # Image Formation (required)
        self._image_formation = QComboBox()
        self._image_formation.addItems(image_formation_registry.list())
        layout.addRow("Image Formation:", self._image_formation)

        # Motion Compensation (optional)
        self._moco = self._make_optional_combo(moco_registry)
        layout.addRow("Motion Compensation:", self._moco)

        # Autofocus (optional)
        self._autofocus = self._make_optional_combo(autofocus_registry)
        layout.addRow("Autofocus:", self._autofocus)

        # Geocoding (optional)
        self._geocoding = self._make_optional_combo(geocoding_registry)
        layout.addRow("Geocoding:", self._geocoding)

        # Polarimetric Decomposition (optional)
        self._polarimetric_decomposition = self._make_optional_combo(polarimetry_registry)
        layout.addRow("Polarimetric Decomposition:", self._polarimetric_decomposition)

        # Connect signals
        for combo in (
            self._image_formation,
            self._moco,
            self._autofocus,
            self._geocoding,
            self._polarimetric_decomposition,
        ):
            combo.currentIndexChanged.connect(self.config_changed)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_optional_combo(registry) -> QComboBox:
        combo = QComboBox()
        combo.addItem(_NONE_LABEL)
        combo.addItems(registry.list())
        return combo

    @staticmethod
    def _optional_value(combo: QComboBox) -> str | None:
        text = combo.currentText()
        return None if text == _NONE_LABEL else text

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self) -> ProcessingConfig:
        """Build a :class:`ProcessingConfig` from the current selections."""
        return ProcessingConfig(
            image_formation=self._image_formation.currentText(),
            moco=self._optional_value(self._moco),
            autofocus=self._optional_value(self._autofocus),
            geocoding=self._optional_value(self._geocoding),
            polarimetric_decomposition=self._optional_value(self._polarimetric_decomposition),
        )

    def set_config(self, config: ProcessingConfig) -> None:
        """Populate the dropdowns from an existing :class:`ProcessingConfig`."""
        self._image_formation.setCurrentText(config.image_formation)
        self._set_optional(self._moco, config.moco)
        self._set_optional(self._autofocus, config.autofocus)
        self._set_optional(self._geocoding, config.geocoding)
        self._set_optional(self._polarimetric_decomposition, config.polarimetric_decomposition)

    @staticmethod
    def _set_optional(combo: QComboBox, value: str | None) -> None:
        combo.setCurrentText(value if value is not None else _NONE_LABEL)
