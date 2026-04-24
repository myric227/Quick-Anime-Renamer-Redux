import os
import re
import sys

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMenuBar
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtCore import QSettings

# -----------------------
# App Info
# -----------------------
APP_NAME = "Quick Anime Renamer Redux"
APP_VERSION = "1.1.6"

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
        self.cb_episode = QCheckBox()

        for cb, text in (
            (self.cb_brackets, "Remove [ ]"),
            (self.cb_parentheses, "Remove ( )"),
            (self.cb_curly, "Remove { }"),
            (self.cb_underscore, "Replace _ with spaces"),
            (self.cb_dots, "Replace . with spaces"),
            (self.cb_episode, "Auto-detect episode numbers"),
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
            self.cb_episode,
            settings_bool(self.settings.value("episodes"), True)
        )

    def on_option_changed(self):
        self.save_settings()
        self.preview_files()

    def save_settings(self):
        self.settings.setValue("remove_brackets", self.cb_brackets.isChecked())
        self.settings.setValue("remove_parentheses", self.cb_parentheses.isChecked())
        self.settings.setValue("remove_curly", self.cb_curly.isChecked())
        self.settings.setValue("underscores", self.cb_underscore.isChecked())
        self.settings.setValue("dots", self.cb_dots.isChecked())
        self.settings.setValue("episodes", self.cb_episode.isChecked())
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

    # -----------------------
    # Episode detection
    # -----------------------
    def detect_episode(self, name):
        m = re.search(r"[sS](\d{1,2})[eE](\d{1,4})", name)
        if m:
            return m.group(1), m.group(2)
        m = re.search(r"\b[eE][pP]? ?(\d{1,4})\b", name)
        if m:
            return None, m.group(1)
        return None, None

    # -----------------------
    # Rename logic
    # -----------------------
    def clean_name(self, filename):
        name, ext = os.path.splitext(filename)
        season, ep = self.detect_episode(name) if self.cb_episode.isChecked() else (None, None)

        if self.cb_brackets.isChecked():
            name = re.sub(r"\[.*?\]", "", name)
        if self.cb_parentheses.isChecked():
            name = re.sub(r"\(.*?\)", "", name)
        if self.cb_curly.isChecked():
            name = re.sub(r"\{.*?\}", "", name)

        name = name.replace("_", " ").replace(".", " ")
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
        for f in self.files:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(os.path.basename(f)))
            self.table.setItem(row, 1, QTableWidgetItem(self.clean_name(os.path.basename(f))))

    # -----------------------
    # Apply / Undo
    # -----------------------
    def apply_rename(self):
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


# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("quick_anime_renamer_redux.ico")))
    window = AnimeRenamer()
    window.show()
    sys.exit(app.exec())
