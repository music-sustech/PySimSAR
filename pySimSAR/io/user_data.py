"""Cross-platform user data directory management for PySimSAR.

Resolves user-specific data paths using platformdirs:
  - Windows: %APPDATA%/PySimSAR/
  - macOS:   ~/Library/Application Support/PySimSAR/
  - Linux:   ~/.local/share/PySimSAR/
"""

from __future__ import annotations

import json
from pathlib import Path

from platformdirs import user_data_dir

_APP_NAME = "PySimSAR"
_APP_AUTHOR = "PySimSAR"

# Preset sub-categories
_PRESET_CATEGORIES = ("antennas", "waveforms", "platforms", "sensors", "full-scenario")


class UserDataDir:
    """Manages the cross-platform user data directory.

    Creates the directory structure on first access:
        {user_data_dir}/PySimSAR/
        ├── presets/
        │   ├── antennas/
        │   ├── waveforms/
        │   ├── platforms/
        │   ├── sensors/
        │   └── full-scenario/
        └── preferences.json
    """

    def __init__(self) -> None:
        self._root = Path(user_data_dir(_APP_NAME, _APP_AUTHOR))

    @property
    def root(self) -> Path:
        """Root user data directory."""
        return self._root

    @property
    def presets_dir(self) -> Path:
        """Directory containing user presets."""
        return self._root / "presets"

    @property
    def preferences_path(self) -> Path:
        """Path to preferences.json."""
        return self._root / "preferences.json"

    def ensure_structure(self) -> None:
        """Create the directory structure if it doesn't exist."""
        self._root.mkdir(parents=True, exist_ok=True)
        for category in _PRESET_CATEGORIES:
            (self.presets_dir / category).mkdir(parents=True, exist_ok=True)

    # -- Preferences ----------------------------------------------------------

    def load_preferences(self) -> dict:
        """Load preferences from disk. Returns defaults if file missing."""
        defaults = {
            "tooltips_enabled": True,
            "recent_projects": [],
            "window_geometry": {},
            "default_colormap": "gray",
            "default_dynamic_range_dB": 40.0,
        }
        if self.preferences_path.exists():
            try:
                with open(self.preferences_path, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                defaults.update(stored)
            except (json.JSONDecodeError, OSError):
                pass
        return defaults

    def save_preferences(self, prefs: dict) -> None:
        """Write preferences to disk."""
        self.ensure_structure()
        with open(self.preferences_path, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2, default=str)

    # -- Presets --------------------------------------------------------------

    def list_presets(self, category: str, tier: str = "user") -> list[dict]:
        """List presets in a category.

        Parameters
        ----------
        category : str
            One of the preset categories.
        tier : str
            "user" for user presets, "system" for shipped presets.

        Returns
        -------
        list[dict]
            List of {"name": ..., "path": ..., "tier": ...} dicts.
        """
        if tier == "system":
            base = Path(__file__).resolve().parent.parent / "presets" / category
        else:
            base = self.presets_dir / category

        results = []
        if base.exists():
            for p in sorted(base.glob("*.json")):
                results.append({
                    "name": p.stem,
                    "path": p,
                    "tier": tier,
                })
        return results

    def load_preset(self, path: Path) -> dict:
        """Load a preset from a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_user_preset(self, category: str, name: str, params: dict) -> Path:
        """Save a user preset.

        Returns the path to the saved file.
        """
        self.ensure_structure()
        dest = self.presets_dir / category / f"{name}.json"
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(params, f, indent=2)
        return dest

    def delete_user_preset(self, path: Path) -> None:
        """Delete a user preset file."""
        if path.exists() and str(self.presets_dir) in str(path):
            path.unlink()

    def duplicate_to_user(self, system_path: Path, new_name: str) -> Path:
        """Copy a system preset to user presets."""
        data = self.load_preset(system_path)
        # Determine category from path
        category = system_path.parent.name
        return self.save_user_preset(category, new_name, data)


__all__ = ["UserDataDir"]
