import json
from pathlib import Path
from unittest.mock import patch
import pytest
from pySimSAR.io.user_data import UserDataDir

@pytest.fixture
def user_dir(tmp_path):
    """UserDataDir backed by a temp directory."""
    ud = UserDataDir()
    ud._root = tmp_path / "PySimSAR"
    return ud

def test_ensure_structure(user_dir):
    user_dir.ensure_structure()
    assert user_dir.root.exists()
    assert (user_dir.presets_dir / "antennas").is_dir()
    assert (user_dir.presets_dir / "waveforms").is_dir()

def test_preferences_defaults(user_dir):
    prefs = user_dir.load_preferences()
    assert prefs["tooltips_enabled"] is True
    assert prefs["default_colormap"] == "gray"

def test_preferences_roundtrip(user_dir):
    user_dir.ensure_structure()
    prefs = {"tooltips_enabled": False, "default_colormap": "viridis"}
    user_dir.save_preferences(prefs)
    loaded = user_dir.load_preferences()
    assert loaded["tooltips_enabled"] is False
    assert loaded["default_colormap"] == "viridis"

def test_preset_save_load_delete(user_dir):
    user_dir.ensure_structure()
    params = {"carrier_freq": 9.65e9, "prf": 1000}
    path = user_dir.save_user_preset("sensors", "x_band", params)
    assert path.exists()
    loaded = user_dir.load_preset(path)
    assert loaded == params

    presets = user_dir.list_presets("sensors", "user")
    assert len(presets) == 1
    assert presets[0]["name"] == "x_band"

    user_dir.delete_user_preset(path)
    assert not path.exists()
