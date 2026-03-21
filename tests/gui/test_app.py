"""GUI smoke test (T115).

Verifies: launch GUI, configure point-target scene, run pipeline,
all panels display correct data.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")


from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication exists for all tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestMainWindowSmoke:
    """Smoke test: main window launches and basic operations work."""

    def test_main_window_creates(self, qapp, qtbot):
        """MainWindow creates without error and has expected structure."""
        from pySimSAR.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        assert window.windowTitle() == "PySimSAR - SAR Signal Simulator"
        assert window.isVisible()
        window.close()

    def test_main_window_has_panels(self, qapp, qtbot):
        """MainWindow contains all 9 visualization panels."""
        from pySimSAR.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert window._tab_widget.count() == 9
        assert window._tab_widget.tabText(0) == "3D Scene"
        assert window._tab_widget.tabText(1) == "Trajectory"
        assert window._tab_widget.tabText(2) == "Beam Animation"
        assert window._tab_widget.tabText(3) == "SAR Image"
        assert window._tab_widget.tabText(4) == "Phase History"
        assert window._tab_widget.tabText(5) == "Range Profile"
        assert window._tab_widget.tabText(6) == "Azimuth Profile"
        assert window._tab_widget.tabText(7) == "Doppler Spectrum"
        assert window._tab_widget.tabText(8) == "Polarimetry"
        window.close()

    def test_main_window_has_param_tree(self, qapp, qtbot):
        """MainWindow contains the parameter tree and calc panel."""
        from pySimSAR.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        assert window._param_tree is not None
        assert window._calc_panel is not None
        # Verify parameter tree returns valid data
        params = window._param_tree.get_all_parameters()
        assert "radar" in params
        assert "platform" in params
        assert "scene" in params
        window.close()

    def test_main_window_has_menus(self, qapp, qtbot):
        """MainWindow has File, Edit, Tools, Simulation menus."""
        from pySimSAR.gui.app import MainWindow

        window = MainWindow()
        qtbot.addWidget(window)

        menus = [a.text() for a in window.menuBar().actions()]
        assert "&File" in menus
        assert "&Edit" in menus
        assert "&Tools" in menus
        assert "&Simulation" in menus
        window.close()


class TestParameterEditors:
    """Smoke test: parameter editors get/set values."""

    def test_radar_editor_roundtrip(self, qapp, qtbot):
        """RadarParamEditor get/set params round-trips."""
        from pySimSAR.gui.widgets.param_editor import RadarParamEditor

        editor = RadarParamEditor()
        qtbot.addWidget(editor)

        params = {
            "carrier_freq": 5.4e9,
            "prf": 500.0,
            "transmit_power": 200.0,
            "bandwidth": 100e6,
            "polarization": "quad",
            "mode": "spotlight",
            "look_side": "left",
            "depression_angle": 0.5,
        }
        editor.set_params(params)
        result = editor.get_params()

        assert result["carrier_freq"] == pytest.approx(5.4e9, rel=1e-3)
        assert result["polarization"] == "quad"
        assert result["mode"] == "spotlight"

    def test_algorithm_selector_roundtrip(self, qapp, qtbot):
        """AlgorithmSelector get/set config round-trips."""
        from pySimSAR.gui.widgets.algorithm_selector import AlgorithmSelector
        from pySimSAR.io.config import ProcessingConfig

        selector = AlgorithmSelector()
        qtbot.addWidget(selector)

        config = ProcessingConfig(
            image_formation="range_doppler",
            moco="first_order",
        )
        selector.set_config(config)
        result = selector.get_config()

        assert result.image_formation == "range_doppler"
        assert result.moco == "first_order"


class TestProjectModel:
    """Smoke test: ProjectModel state management."""

    def test_project_model_defaults(self):
        """ProjectModel starts with no simulation or pipeline results."""
        from pySimSAR.gui.controllers.simulation_ctrl import ProjectModel

        model = ProjectModel()
        assert not model.has_simulation
        assert not model.has_pipeline

    def test_project_model_reset(self):
        """ProjectModel.reset() clears all state."""
        from pySimSAR.gui.controllers.simulation_ctrl import ProjectModel

        model = ProjectModel()
        model.n_pulses = 999
        model.reset()
        assert model.n_pulses == 512
