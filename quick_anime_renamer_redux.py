import os
import re
import sys

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMenuBar
)
from PySide6.QtGui import QAction, QBrush, QColor, QIcon
from PySide6.QtCore import QSettings, Qt

# -----------------------
# App Info
# -----------------------
APP_NAME = "Quick Anime Renamer Redux"
APP_VERSION = "1.2.0"

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".wmv"}


def get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(filename):
    if getattr(sys, "frozen", False):
        return os.path.join(getattr(sys, "_MEIPASS", get_base_dir()), filename)
    return os.path.join(get_base_dir(), filename)


def get_settings_path():
    """INI file next to script or EXE."""
    return os.path.join(get_base_dir(), "QuickAnimeRenamerRedux.ini")


def settings_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class AnimeRenamer(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setWindowIcon(QIcon(resource_path("quick_anime_renamer_redux.ico")))
        self.resize(820, 520)

        self.settings = QSettings(get_settings_path(), QSettings.IniFormat)

        self.files = []
        self.rename_history = []
        self.conflict_rows = set()

        self.build_ui()
        self.load_settings()

    # -----------------------
    # UI
    # -----------------------
    def build_ui(self):
        main = QVBoxLayout()

        menu = QMenuBar()
        help_menu = menu.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        main.setMenuBar(menu)

        title = QLabel("Drag & Drop Anime Videos or Select a Folder")
        title.setStyleSheet("font-size:16px;font-weight:bold;")
        main.addWidget(title)

        self.cb_brackets = QCheckBox()
        self.cb_parentheses = QCheckBox()
        self.cb_curly = QCheckBox()
        self.cb_underscore = QCheckBox()
        self.cb_dots = QCheckBox()
        self.cb_versions = QCheckBox()
        self.cb_episode = QCheckBox()
        self.cb_autoload = QCheckBox()

        for cb, text in (
            (self.cb_brackets, "Remove [ ]"),
            (self.cb_parentheses, "Remove ( )"),
            (self.cb_curly, "Remove { }"),
            (self.cb_underscore, "Replace _ with spaces"),
            (self.cb_dots, "Replace . with spaces"),
            (self.cb_versions, "Remove version tags like v2"),
            (self.cb_episode, "Auto-detect episode numbers"),
            (self.cb_autoload, "Auto-load last directory on startup"),
        ):
            row = QHBoxLayout()
            row.addWidget(cb)
            row.addWidget(QLabel(text))
            row.addStretch(1)
            main.addLayout(row)
            cb.stateChanged.connect(self.on_option_changed)

        buttons = QHBoxLayout()
        self.btn_folder = QPushButton("Select Folder")
        self.btn_apply = QPushButton("Apply Rename")
        self.btn_undo = QPushButton("Undo Last Rename")
        self.btn_undo.setEnabled(False)

        for b in (self.btn_folder, self.btn_apply, self.btn_undo):
            buttons.addWidget(b)

        main.addLayout(buttons)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Original Name", "New Name"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        main.addWidget(self.table)

        self.setLayout(main)
        self.setAcceptDrops(True)

        self.btn_folder.clicked.connect(self.select_folder)
        self.btn_apply.clicked.connect(self.apply_rename)
        self.btn_undo.clicked.connect(self.undo_rename)

    # -----------------------
    # Settings (FIXED)
    # -----------------------
    def set_checkbox_safely(self, checkbox, value):
        checkbox.blockSignals(True)
        checkbox.setChecked(value)
        checkbox.blockSignals(False)

    def load_settings(self):
        self.set_checkbox_safely(
            self.cb_brackets,
            settings_bool(self.settings.value("remove_brackets"), True)
        )
        self.set_checkbox_safely(
            self.cb_parentheses,
            settings_bool(self.settings.value("remove_parentheses"), True)
        )
        self.set_checkbox_safely(
            self.cb_curly,
            settings_bool(self.settings.value("remove_curly"), False)
        )
        self.set_checkbox_safely(
            self.cb_underscore,
            settings_bool(self.settings.value("underscores"), True)
        )
        self.set_checkbox_safely(
            self.cb_dots,
            settings_bool(self.settings.value("dots"), False)
        )
        self.set_checkbox_safely(
            self.cb_versions,
            settings_bool(self.settings.value("versions"), True)
        )
        self.set_checkbox_safely(
            self.cb_episode,
            settings_bool(self.settings.value("episodes"), True)
        )
        self.set_checkbox_safely(
            self.cb_autoload,
            settings_bool(self.settings.value("autoload_last_dir"), False)
        )

        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        if self.cb_autoload.isChecked():
            self.auto_load_last_directory()

    def on_option_changed(self):
        self.save_settings()
        self.preview_files()

    def save_settings(self):
        self.settings.setValue("remove_brackets", self.cb_brackets.isChecked())
        self.settings.setValue("remove_parentheses", self.cb_parentheses.isChecked())
        self.settings.setValue("remove_curly", self.cb_curly.isChecked())
        self.settings.setValue("underscores", self.cb_underscore.isChecked())
        self.settings.setValue("dots", self.cb_dots.isChecked())
        self.settings.setValue("versions", self.cb_versions.isChecked())
        self.settings.setValue("episodes", self.cb_episode.isChecked())
        self.settings.setValue("autoload_last_dir", self.cb_autoload.isChecked())
        self.settings.sync()

    # -----------------------
    # Drag & Drop
    # -----------------------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.files.clear()
        self.table.setRowCount(0)

        last_dir = None
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path) and self.is_video(path):
                self.files.append(path)
                last_dir = os.path.dirname(path)

        if last_dir:
            self.settings.setValue("last_dir", last_dir)
            self.settings.sync()

        self.preview_files()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.remove_selected_rows()
            return
        super().keyPressEvent(event)

    # -----------------------
    # File handling
    # -----------------------
    def is_video(self, path):
        return os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS

    def select_folder(self):
        start = self.settings.value("last_dir", "")
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", start)
        if folder:
            self.settings.setValue("last_dir", folder)
            self.settings.sync()
            self.files = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if self.is_video(f)
            ]
            self.preview_files()

    def auto_load_last_directory(self):
        folder = self.settings.value("last_dir", "")
        if not folder or not os.path.isdir(folder):
            return
        self.files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if self.is_video(f)
        ]
        self.preview_files()

    # -----------------------
    # Episode detection
    # -----------------------
    def detect_episode(self, name):
        m = re.search(r"[sS](\d{1,2})[eE](\d{1,4})", name)
        if m:
            return m.group(1), m.group(2), m.group(0)
        m = re.search(r"\b[eE][pP]? ?(\d{1,4})\b", name)
        if m:
            return None, m.group(1), m.group(0)
        return None, None, None

    # -----------------------
    # Rename logic
    # -----------------------
    def clean_name(self, filename):
        name, ext = os.path.splitext(filename)
        season, ep, episode_token = self.detect_episode(name) if self.cb_episode.isChecked() else (None, None, None)

        if self.cb_brackets.isChecked():
            name = re.sub(r"\[.*?\]", "", name)
        if self.cb_parentheses.isChecked():
            name = re.sub(r"\(.*?\)", "", name)
        if self.cb_curly.isChecked():
            name = re.sub(r"\{.*?\}", "", name)
        if self.cb_versions.isChecked():
            # Remove both standalone versions like " v2 " and attached forms like "04v3".
            name = re.sub(r"(?i)(\d+)v\d{1,3}(?=$|[\s._-])", r"\1", name)
            name = re.sub(r"(?i)(?:^|[\s._-])v\d{1,3}(?=$|[\s._-])", " ", name)
        if episode_token:
            name = re.sub(re.escape(episode_token), " ", name, flags=re.IGNORECASE)

        if self.cb_underscore.isChecked():
            name = name.replace("_", " ")
        if self.cb_dots.isChecked():
            name = name.replace(".", " ")
        name = re.sub(r"\s+", " ", name).strip(" -")

        if ep:
            if season:
                return f"{name} - S{season.zfill(2)} - {ep}{ext}"
            return f"{name} - {ep}{ext}"

        return f"{name}{ext}"

    # -----------------------
    # Preview
    # -----------------------
    def preview_files(self):
        self.table.setRowCount(0)
        preview_names = [self.clean_name(os.path.basename(f)) for f in self.files]

        targets = {}
        for index, f in enumerate(self.files):
            new_path = os.path.join(os.path.dirname(f), preview_names[index])
            targets.setdefault(new_path, []).append(index)

        conflicts = set()
        for target_path, indices in targets.items():
            current_owner = next((i for i, f in enumerate(self.files) if f == target_path), None)

            if len(indices) > 1:
                if current_owner is not None and preview_names[current_owner] == os.path.basename(self.files[current_owner]):
                    conflicts.update(i for i in indices if i != current_owner)
                else:
                    conflicts.update(indices)

            if os.path.exists(target_path):
                if current_owner is None:
                    conflicts.update(indices)
                elif preview_names[current_owner] != os.path.basename(self.files[current_owner]):
                    conflicts.update(indices)

        self.conflict_rows = conflicts
        for f in self.files:
            row = self.table.rowCount()
            self.table.insertRow(row)
            original_item = QTableWidgetItem(os.path.basename(f))
            renamed_item = QTableWidgetItem(preview_names[row])
            if row in self.conflict_rows:
                # Keep conflict rows readable in both light and dark themes.
                highlight = QBrush(QColor("#4b3b1d"))
                warning_text = QBrush(QColor("#ffffff"))
                original_item.setBackground(highlight)
                renamed_item.setBackground(highlight)
                original_item.setForeground(warning_text)
                renamed_item.setForeground(warning_text)
                original_item.setToolTip("Filename conflict detected")
                renamed_item.setToolTip("Filename conflict detected")
            self.table.setItem(row, 0, original_item)
            self.table.setItem(row, 1, renamed_item)

    def remove_selected_rows(self):
        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()}, reverse=True)
        if not rows:
            return
        for row in rows:
            if 0 <= row < len(self.files):
                del self.files[row]
        self.preview_files()

    # -----------------------
    # Apply / Undo
    # -----------------------
    def apply_rename(self):
        if self.conflict_rows:
            QMessageBox.warning(
                self,
                "Conflicts detected",
                "Fix the highlighted filename conflicts before renaming."
            )
            return

        self.rename_history.clear()
        for f in self.files:
            new_name = self.clean_name(os.path.basename(f))
            new_path = os.path.join(os.path.dirname(f), new_name)
            if f != new_path:
                os.rename(f, new_path)
                self.rename_history.append((f, new_path))
        if self.rename_history:
            self.btn_undo.setEnabled(True)
            QMessageBox.information(self, "Done", "Files renamed.")

    def undo_rename(self):
        for old, new in reversed(self.rename_history):
            if os.path.exists(new):
                os.rename(new, old)
        self.rename_history.clear()
        self.btn_undo.setEnabled(False)

    # -----------------------
    # About
    # -----------------------
    def show_about(self):
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "Created by Justin Morland\n\n"
            "Inspired by Quick Anime Renamer\n"
            "Not affiliated."
        )

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.sync()
        super().closeEvent(event)


# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("quick_anime_renamer_redux.ico")))
    window = AnimeRenamer()
    window.show()
    sys.exit(app.exec())
