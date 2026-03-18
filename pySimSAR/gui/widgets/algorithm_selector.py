"""Algorithm selector widget for the SAR processing pipeline GUI."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)


def _no_scroll_unless_focused(widget: QWidget) -> None:
    """Configure *widget* so that mouse-wheel changes its value only when focused."""
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    original_wheel = widget.wheelEvent

    def _wheel(event):  # type: ignore[override]
        if not widget.hasFocus():
            event.ignore()
            return
        original_wheel(event)

    widget.wheelEvent = _wheel  # type: ignore[assignment]

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
        _no_scroll_unless_focused(self._image_formation)
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

        # Description
        self._description = QLineEdit()
        self._description.setPlaceholderText("Optional description")
        layout.addRow("Description:", self._description)

        # --- Autofocus parameter widgets ---
        self._af_params_group = QGroupBox("Algorithm Parameters")
        af_params_layout = QFormLayout(self._af_params_group)

        self._af_max_iterations_label = QLabel("Max Iterations:")
        self._af_max_iterations = QSpinBox()
        self._af_max_iterations.setRange(1, 100)
        self._af_max_iterations.setValue(10)
        _no_scroll_unless_focused(self._af_max_iterations)
        af_params_layout.addRow(self._af_max_iterations_label, self._af_max_iterations)

        self._af_poly_order_label = QLabel("Poly Order:")
        self._af_poly_order = QSpinBox()
        self._af_poly_order.setRange(1, 10)
        self._af_poly_order.setValue(4)
        _no_scroll_unless_focused(self._af_poly_order)
        af_params_layout.addRow(self._af_poly_order_label, self._af_poly_order)

        self._af_n_subapertures_label = QLabel("N Subapertures:")
        self._af_n_subapertures = QSpinBox()
        self._af_n_subapertures.setRange(2, 32)
        self._af_n_subapertures.setValue(4)
        _no_scroll_unless_focused(self._af_n_subapertures)
        af_params_layout.addRow(self._af_n_subapertures_label, self._af_n_subapertures)

        layout.addRow(self._af_params_group)

        # Initial visibility
        self._update_autofocus_params(self._autofocus.currentText())

        # Connect autofocus combo to parameter visibility
        self._autofocus.currentTextChanged.connect(self._update_autofocus_params)

        # Connect signals
        for combo in (
            self._image_formation,
            self._moco,
            self._autofocus,
            self._geocoding,
            self._polarimetric_decomposition,
        ):
            combo.currentIndexChanged.connect(self.config_changed)
        self._description.textChanged.connect(self.config_changed)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_optional_combo(registry) -> QComboBox:
        combo = QComboBox()
        combo.addItem(_NONE_LABEL)
        combo.addItems(registry.list())
        _no_scroll_unless_focused(combo)
        return combo

    @staticmethod
    def _optional_value(combo: QComboBox) -> str | None:
        text = combo.currentText()
        return None if text == _NONE_LABEL else text

    def _update_autofocus_params(self, algorithm: str) -> None:
        """Show/hide autofocus parameter fields based on selected algorithm."""
        af = algorithm.lower() if algorithm else ""
        has_params = af in ("pga", "min_entropy", "mda")

        self._af_params_group.setVisible(has_params)

        # max_iterations: PGA, MinEntropy, MDA
        show_max_iter = af in ("pga", "min_entropy", "mda")
        self._af_max_iterations_label.setVisible(show_max_iter)
        self._af_max_iterations.setVisible(show_max_iter)

        # Set appropriate default for max_iterations based on algorithm
        if af == "pga" or af == "mda":
            self._af_max_iterations.setValue(10)
        elif af == "min_entropy":
            self._af_max_iterations.setValue(20)

        # poly_order: MinEntropy only
        show_poly = af == "min_entropy"
        self._af_poly_order_label.setVisible(show_poly)
        self._af_poly_order.setVisible(show_poly)

        # n_subapertures: MDA only
        show_sub = af == "mda"
        self._af_n_subapertures_label.setVisible(show_sub)
        self._af_n_subapertures.setVisible(show_sub)

    def _get_autofocus_params(self) -> dict | None:
        """Build autofocus params dict from visible fields."""
        af = self._optional_value(self._autofocus)
        if af is None:
            return None
        af_lower = af.lower()
        params: dict = {}
        if af_lower in ("pga", "min_entropy", "mda"):
            params["max_iterations"] = self._af_max_iterations.value()
        if af_lower == "min_entropy":
            params["poly_order"] = self._af_poly_order.value()
        if af_lower == "mda":
            params["n_subapertures"] = self._af_n_subapertures.value()
        return params if params else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self) -> ProcessingConfig:
        """Build a :class:`ProcessingConfig` from the current selections."""
        return ProcessingConfig(
            image_formation=self._image_formation.currentText(),
            moco=self._optional_value(self._moco),
            autofocus=self._optional_value(self._autofocus),
            autofocus_params=self._get_autofocus_params(),
            geocoding=self._optional_value(self._geocoding),
            polarimetric_decomposition=self._optional_value(self._polarimetric_decomposition),
            description=self._description.text(),
        )

    def set_config(self, config: ProcessingConfig) -> None:
        """Populate the dropdowns from an existing :class:`ProcessingConfig`."""
        self._image_formation.setCurrentText(config.image_formation)
        self._set_optional(self._moco, config.moco)
        self._set_optional(self._autofocus, config.autofocus)
        self._set_optional(self._geocoding, config.geocoding)
        self._set_optional(self._polarimetric_decomposition, config.polarimetric_decomposition)

        # Populate autofocus parameter fields
        af_params = getattr(config, "autofocus_params", None) or {}
        if "max_iterations" in af_params:
            self._af_max_iterations.setValue(af_params["max_iterations"])
        if "poly_order" in af_params:
            self._af_poly_order.setValue(af_params["poly_order"])
        if "n_subapertures" in af_params:
            self._af_n_subapertures.setValue(af_params["n_subapertures"])

        # Populate description
        desc = getattr(config, "description", "")
        self._description.setText(desc or "")

    @staticmethod
    def _set_optional(combo: QComboBox, value: str | None) -> None:
        combo.setCurrentText(value if value is not None else _NONE_LABEL)
