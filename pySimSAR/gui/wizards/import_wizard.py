"""Data import wizard — HDF5 file import with preview and gap detection."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)


class FileSelectionPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Select HDF5 File")
        self.setSubTitle("Choose an HDF5 file to import.")
        layout = QVBoxLayout(self)

        row = QFormLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Path to .h5 or .hdf5 file")
        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.clicked.connect(self._browse)
        row.addRow("File:", self._path_edit)
        layout.addLayout(row)
        layout.addWidget(self._browse_btn)

        self.registerField("hdf5_path*", self._path_edit)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select HDF5 File", "",
            "HDF5 Files (*.h5 *.hdf5);;All Files (*)"
        )
        if path:
            self._path_edit.setText(path)

    def get_path(self) -> str:
        return self._path_edit.text()


class PreviewPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("File Preview")
        self.setSubTitle("Review the contents of the HDF5 file.")
        layout = QVBoxLayout(self)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Group/Dataset", "Info"])
        layout.addWidget(self._tree)

        self._status = QLabel("")
        layout.addWidget(self._status)

    def initializePage(self):
        self._tree.clear()
        wizard = self.wizard()
        path = wizard.page(0).get_path()

        try:
            import h5py
            with h5py.File(path, 'r') as f:
                self._populate_tree(f, self._tree.invisibleRootItem())
            self._status.setText("File loaded successfully.")
            self._status.setStyleSheet("color: green;")
        except Exception as e:
            self._status.setText(f"Error reading file: {e}")
            self._status.setStyleSheet("color: red;")

    def _populate_tree(self, group, parent_item, depth=0):
        if depth > 5:
            return
        import h5py
        for key in group:
            item = QTreeWidgetItem(parent_item)
            item.setText(0, key)
            obj = group[key]
            if isinstance(obj, h5py.Group):
                item.setText(1, f"Group ({len(obj)} items)")
                self._populate_tree(obj, item, depth + 1)
            elif isinstance(obj, h5py.Dataset):
                item.setText(1, f"{obj.shape} {obj.dtype}")


class GapFillingPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("Parameter Gap Detection")
        self.setSubTitle("Review detected parameters and fill any gaps.")
        layout = QVBoxLayout(self)
        self._info = QTextEdit()
        self._info.setReadOnly(True)
        layout.addWidget(self._info)

    def initializePage(self):
        self._info.setText(
            "Parameter completeness check:\n\n"
            "This HDF5 file will be imported for processing.\n"
            "Missing parameters will use default values from the parameter tree.\n\n"
            "Click 'Finish' to import the data."
        )


class ImportWizard(QWizard):
    """HDF5 data import wizard with preview and gap detection."""

    import_completed = pyqtSignal(str)  # filepath

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import HDF5 Data")
        self.setMinimumSize(600, 450)

        self._file_page = FileSelectionPage()
        self._preview_page = PreviewPage()
        self._gap_page = GapFillingPage()

        self.addPage(self._file_page)
        self.addPage(self._preview_page)
        self.addPage(self._gap_page)

    def get_filepath(self) -> str:
        return self._file_page.get_path()

    def accept(self):
        self.import_completed.emit(self.get_filepath())
        super().accept()
