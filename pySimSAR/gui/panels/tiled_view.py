"""Tiled/split visualization panel manager."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QSplitter,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class TiledViewManager(QWidget):
    """Manages tiled visualization with split support.

    Supports a main tab bar with a split button that divides the view
    into 2-4 panes, each with its own panel selector.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._panels: dict[str, type] = {}
        self._panel_instances: list[QWidget] = []
        self._panel_factories: dict[str, callable] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar with split controls
        toolbar = QHBoxLayout()
        self._split_h_btn = QToolButton()
        self._split_h_btn.setText("Split \u2194")
        self._split_h_btn.setToolTip("Split horizontally")
        self._split_h_btn.clicked.connect(lambda: self._split(Qt.Orientation.Horizontal))
        toolbar.addWidget(self._split_h_btn)

        self._split_v_btn = QToolButton()
        self._split_v_btn.setText("Split \u2195")
        self._split_v_btn.setToolTip("Split vertically")
        self._split_v_btn.clicked.connect(lambda: self._split(Qt.Orientation.Vertical))
        toolbar.addWidget(self._split_v_btn)

        self._unsplit_btn = QToolButton()
        self._unsplit_btn.setText("Unsplit")
        self._unsplit_btn.setToolTip("Remove split")
        self._unsplit_btn.clicked.connect(self._unsplit)
        self._unsplit_btn.setEnabled(False)
        toolbar.addWidget(self._unsplit_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Content area
        self._content_layout = QVBoxLayout()
        layout.addLayout(self._content_layout)

        # Primary tab widget
        self._primary_tabs = QTabWidget()
        self._content_layout.addWidget(self._primary_tabs)
        self._splitter = None
        self._secondary_tabs = None

    def register_panel(self, name: str, panel: QWidget) -> None:
        """Register a panel by name. The first registered becomes the primary."""
        self._primary_tabs.addTab(panel, name)
        self._panel_instances.append(panel)

    def _split(self, orientation: Qt.Orientation) -> None:
        """Split the view into two panes."""
        if self._splitter is not None:
            return  # Already split

        self._content_layout.removeWidget(self._primary_tabs)

        self._splitter = QSplitter(orientation)
        self._splitter.addWidget(self._primary_tabs)

        self._secondary_tabs = QTabWidget()
        # Add placeholder tabs matching primary
        for i in range(self._primary_tabs.count()):
            name = self._primary_tabs.tabText(i)
            placeholder = QWidget()
            self._secondary_tabs.addTab(placeholder, name)

        self._splitter.addWidget(self._secondary_tabs)
        self._content_layout.addWidget(self._splitter)
        self._unsplit_btn.setEnabled(True)

    def _unsplit(self) -> None:
        """Remove split and restore single-pane view."""
        if self._splitter is None:
            return

        self._splitter.setParent(None)  # type: ignore[arg-type]
        if self._secondary_tabs is not None:
            self._secondary_tabs.setParent(None)  # type: ignore[arg-type]
            self._secondary_tabs = None

        self._content_layout.addWidget(self._primary_tabs)
        self._splitter = None
        self._unsplit_btn.setEnabled(False)

    def set_current_panel(self, name: str) -> None:
        """Switch the primary tabs to show the named panel."""
        for i in range(self._primary_tabs.count()):
            if self._primary_tabs.tabText(i) == name:
                self._primary_tabs.setCurrentIndex(i)
                break
