"""Two-tier preset browser dialog (system read-only + user read-write)."""
from __future__ import annotations
from pathlib import Path
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QInputDialog, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QSplitter,
    QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)
from pySimSAR.io.user_data import UserDataDir

_CATEGORIES = ["antennas", "waveforms", "platforms", "sensors", "full-scenario"]


class PresetBrowserDialog(QDialog):
    """Browse, apply, save, and manage parameter presets.

    Signals
    -------
    preset_applied(dict)
        Emitted when user clicks Apply — carries the full parameter dict.
    """

    preset_applied = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preset Browser")
        self.setMinimumSize(700, 450)

        self._user_data = UserDataDir()
        self._user_data.ensure_structure()
        self._current_preset_path: Path | None = None
        self._current_preset_data: dict | None = None
        self._current_tier: str = "system"

        self._build_ui()
        self._refresh_categories()

    def _build_ui(self):
        layout = QHBoxLayout(self)

        # Left: category tree
        self._cat_tree = QTreeWidget()
        self._cat_tree.setHeaderLabel("Categories")
        self._cat_tree.setMaximumWidth(180)
        self._cat_tree.currentItemChanged.connect(self._on_category_changed)
        layout.addWidget(self._cat_tree)

        # Middle: preset list
        middle = QVBoxLayout()
        self._preset_list = QListWidget()
        self._preset_list.currentItemChanged.connect(self._on_preset_selected)
        middle.addWidget(QLabel("Presets:"))
        middle.addWidget(self._preset_list)
        layout.addLayout(middle)

        # Right: preview + actions
        right = QVBoxLayout()
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMaximumWidth(250)
        right.addWidget(QLabel("Preview:"))
        right.addWidget(self._preview)

        # Buttons
        self._btn_apply = QPushButton("Apply")
        self._btn_apply.clicked.connect(self._on_apply)
        self._btn_apply.setEnabled(False)
        right.addWidget(self._btn_apply)

        self._btn_save = QPushButton("Save Current As...")
        self._btn_save.clicked.connect(self._on_save)
        right.addWidget(self._btn_save)

        self._btn_duplicate = QPushButton("Duplicate to User")
        self._btn_duplicate.clicked.connect(self._on_duplicate)
        self._btn_duplicate.setEnabled(False)
        right.addWidget(self._btn_duplicate)

        self._btn_delete = QPushButton("Delete")
        self._btn_delete.clicked.connect(self._on_delete)
        self._btn_delete.setEnabled(False)
        right.addWidget(self._btn_delete)

        layout.addLayout(right)

    def _refresh_categories(self):
        self._cat_tree.clear()
        for cat in _CATEGORIES:
            item = QTreeWidgetItem()
            item.setText(0, cat.replace("-", " ").title())
            item.setData(0, Qt.ItemDataRole.UserRole, cat)
            self._cat_tree.addTopLevelItem(item)

    def _on_category_changed(self, current, previous):
        if current is None:
            return
        category = current.data(0, Qt.ItemDataRole.UserRole)
        self._refresh_preset_list(category)

    def _refresh_preset_list(self, category: str):
        self._preset_list.clear()
        # System presets
        for info in self._user_data.list_presets(category, "system"):
            item = QListWidgetItem(f"🔒 {info['name']}")
            item.setData(Qt.ItemDataRole.UserRole, {"path": info["path"], "tier": "system"})
            self._preset_list.addItem(item)
        # User presets
        for info in self._user_data.list_presets(category, "user"):
            item = QListWidgetItem(f"✏️ {info['name']}")
            item.setData(Qt.ItemDataRole.UserRole, {"path": info["path"], "tier": "user"})
            self._preset_list.addItem(item)

    def _on_preset_selected(self, current, previous):
        if current is None:
            self._preview.clear()
            self._btn_apply.setEnabled(False)
            self._btn_duplicate.setEnabled(False)
            self._btn_delete.setEnabled(False)
            return

        data = current.data(Qt.ItemDataRole.UserRole)
        path = data["path"]
        tier = data["tier"]

        try:
            preset = self._user_data.load_preset(path)
            self._current_preset_path = path
            self._current_preset_data = preset
            self._current_tier = tier

            # Show preview (first few keys)
            lines = []
            for k, v in list(preset.items())[:15]:
                lines.append(f"{k}: {v}")
            if len(preset) > 15:
                lines.append(f"... and {len(preset) - 15} more")
            self._preview.setText("\n".join(lines))
        except Exception as e:
            self._preview.setText(f"Error loading preset: {e}")
            self._current_preset_data = None

        self._btn_apply.setEnabled(self._current_preset_data is not None)
        self._btn_duplicate.setEnabled(tier == "system")
        self._btn_delete.setEnabled(tier == "user")

    def _on_apply(self):
        if self._current_preset_data is not None:
            self.preset_applied.emit(self._current_preset_data)
            self.accept()

    def _on_save(self):
        """Save current parameters as a new user preset."""
        # This will be wired to get current params from the main window
        cat_item = self._cat_tree.currentItem()
        if cat_item is None:
            QMessageBox.warning(self, "Save Preset", "Select a category first.")
            return
        category = cat_item.data(0, Qt.ItemDataRole.UserRole)
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if ok and name:
            # Emit signal or store — for now, create empty placeholder
            self._user_data.save_user_preset(category, name, {})
            self._refresh_preset_list(category)

    def _on_duplicate(self):
        if self._current_preset_path is None:
            return
        name, ok = QInputDialog.getText(
            self, "Duplicate Preset",
            "New preset name:",
            text=self._current_preset_path.stem + "_copy",
        )
        if ok and name:
            self._user_data.duplicate_to_user(self._current_preset_path, name)
            cat_item = self._cat_tree.currentItem()
            if cat_item:
                self._refresh_preset_list(cat_item.data(0, Qt.ItemDataRole.UserRole))

    def _on_delete(self):
        if self._current_preset_path is None or self._current_tier != "user":
            return
        reply = QMessageBox.question(
            self, "Delete Preset",
            f"Delete preset '{self._current_preset_path.stem}'?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._user_data.delete_user_preset(self._current_preset_path)
            cat_item = self._cat_tree.currentItem()
            if cat_item:
                self._refresh_preset_list(cat_item.data(0, Qt.ItemDataRole.UserRole))


__all__ = ["PresetBrowserDialog"]
