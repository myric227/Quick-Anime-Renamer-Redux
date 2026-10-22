from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QMimeData, QPointF, QUrl, Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtTest import QTest

import quick_anime_renamer_redux as renamer


class RenameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([
            "rename-tests", "-platform", "offscreen"
        ])

    def setUp(self):
        # Keep all filesystem tests inside this workspace, including in sandboxes.
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent / ".venv")
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.settings = patch.object(
            renamer, "get_settings_path", return_value=str(self.root / "settings.ini")
        )
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.warning = patch.object(renamer.QMessageBox, "warning").start()
        patch.object(renamer.QMessageBox, "information").start()
        self.addCleanup(patch.stopall)
        self.window = renamer.AnimeRenamer()
        self.addCleanup(self.window.close)

    def video(self, name, contents=b"original video bytes"):
        path = self.root / name
        path.write_bytes(contents)
        return str(path)

    def batch(self, *paths):
        self.window.files = list(paths)
        self.window.preview_files()

    def test_rename_and_undo_preserve_bytes_and_update_paths(self):
        source = self.video("[Group] Show S01E03.mkv")
        target = str(self.root / "Show - S01 - 03.mkv")
        self.batch(source)
        self.window.apply_rename()
        self.assertEqual(self.window.files, [target])
        self.assertEqual(Path(target).read_bytes(), b"original video bytes")
        self.assertFalse(Path(source).exists())
        self.window.undo_rename()
        self.assertEqual(self.window.files, [source])
        self.assertEqual(Path(source).read_bytes(), b"original video bytes")
        self.assertFalse(Path(target).exists())
        self.assertFalse(self.window.btn_undo.isEnabled())

    def test_second_apply_does_not_erase_undo(self):
        source = self.video("[Group] Show.mkv")
        self.batch(source)
        self.window.apply_rename()
        history = self.window.rename_history.copy()
        self.window.apply_rename()
        self.assertEqual(self.window.rename_history, history)
        self.window.undo_rename()
        self.assertTrue(Path(source).exists())

    def test_destination_created_after_preview_is_not_overwritten(self):
        source = self.video("[Group] Show.mkv")
        self.batch(source)
        target = self.video("Show.mkv", b"unrelated existing video")
        self.window.apply_rename()
        self.assertTrue(Path(source).exists())
        self.assertEqual(Path(target).read_bytes(), b"unrelated existing video")
        self.warning.assert_called_once()

    def test_destination_created_during_rename_is_not_overwritten(self):
        source = self.video("[Group] Show.mkv")
        self.batch(source)
        actual_rename = renamer.os.rename

        def create_destination(old, new):
            Path(new).write_bytes(b"racing writer")
            actual_rename(old, new)

        with patch.object(renamer.os, "rename", side_effect=create_destination):
            self.window.apply_rename()
        self.assertTrue(Path(source).exists())
        self.assertEqual((self.root / "Show.mkv").read_bytes(), b"racing writer")
        self.assertEqual(self.window.rename_history, [])
        self.warning.assert_called_once()

    def test_partial_failure_keeps_successes_undoable(self):
        first = self.video("[Group] First.mkv")
        second = self.video("[Group] Second.mkv")
        self.batch(first, second)
        actual_rename = renamer.rename_file

        def fail_second(old, new):
            if old == second:
                raise PermissionError("File locked by another program")
            actual_rename(old, new)

        with patch.object(renamer, "rename_file", side_effect=fail_second):
            self.window.apply_rename()
        self.assertEqual(self.window.files, [str(self.root / "First.mkv"), second])
        self.assertEqual(len(self.window.rename_history), 1)
        self.assertTrue(self.window.btn_undo.isEnabled())
        self.warning.assert_called_once()
        self.window.undo_rename()
        self.assertTrue(Path(first).exists())
        self.assertTrue(Path(second).exists())

    def test_undo_conflict_preserves_history_for_retry(self):
        source = self.video("[Group] Show.mkv")
        self.batch(source)
        self.window.apply_rename()
        Path(source).write_bytes(b"new unrelated file")
        self.window.undo_rename()
        self.assertEqual(Path(source).read_bytes(), b"new unrelated file")
        self.assertEqual(len(self.window.rename_history), 1)
        self.assertTrue(self.window.btn_undo.isEnabled())
        Path(source).unlink()
        self.window.undo_rename()
        self.assertEqual(Path(source).read_bytes(), b"original video bytes")

    def test_partial_undo_can_be_retried(self):
        first = self.video("[Group] First.mkv")
        second = self.video("[Group] Second.mkv")
        self.batch(first, second)
        self.window.apply_rename()
        Path(first).write_bytes(b"conflict")
        self.window.undo_rename()
        self.assertEqual(self.window.files, [str(self.root / "First.mkv"), second])
        self.assertEqual(len(self.window.rename_history), 1)
        Path(first).unlink()
        self.window.undo_rename()
        self.assertEqual(self.window.files, [first, second])

    def test_missing_source_reports_error(self):
        source = self.video("[Group] Show.mkv")
        self.batch(source)
        Path(source).unlink()
        self.window.apply_rename()
        self.warning.assert_called_once()
        self.assertEqual(self.window.rename_history, [])

    def test_missing_undo_source_keeps_history(self):
        source = self.video("[Group] Show.mkv")
        self.batch(source)
        self.window.apply_rename()
        Path(self.window.files[0]).unlink()
        self.window.undo_rename()
        self.warning.assert_called_once()
        self.assertEqual(len(self.window.rename_history), 1)

    def test_case_insensitive_duplicate_targets_are_blocked(self):
        first = self.video("[Group1] Show.mkv")
        second = self.video("[Group2] show.mkv")
        self.batch(first, second)
        self.assertEqual(self.window.conflict_rows, {0, 1})
        self.window.apply_rename()
        self.assertTrue(Path(first).exists())
        self.assertTrue(Path(second).exists())

    def test_reserved_and_empty_names_are_blocked(self):
        first = self.video("[Group] CON.mkv")
        second = self.video("[Group].mkv")
        self.batch(first, second)
        self.assertEqual(self.window.conflict_rows, {0, 1})

    def test_folder_loading_ignores_directories_named_like_videos(self):
        source = self.video("Show.mkv")
        (self.root / "folder.mkv").mkdir()
        self.window.load_directory(str(self.root))
        self.assertEqual(self.window.files, [source])

    def test_folder_error_keeps_current_batch(self):
        source = self.video("Show.mkv")
        self.batch(source)
        self.window.load_directory(str(self.root / "missing"))
        self.assertEqual(self.window.files, [source])
        self.warning.assert_called_once()

    def test_undo_refuses_a_replacement_file(self):
        source = self.video("[Group] Show.mkv")
        self.batch(source)
        self.window.apply_rename()
        target = Path(self.window.files[0])
        target.rename(self.root / "moved-by-another-program.mkv")
        target.write_bytes(b"replacement")
        self.window.undo_rename()
        self.assertEqual(target.read_bytes(), b"replacement")
        self.assertFalse(Path(source).exists())
        self.assertEqual(len(self.window.rename_history), 1)
        self.warning.assert_called_once()

    def test_removed_metadata_does_not_supply_episode_number(self):
        self.assertEqual(
            self.window.clean_name("[Group S01E99] Show S02E01.mkv"),
            "Show - S02 - 01.mkv",
        )

    def test_episode_detection_does_not_split_words_or_long_numbers(self):
        for name in ["ShowS01E03.mkv", "Show S01E12345.mkv", "Show S01E03E04.mkv"]:
            with self.subTest(name=name):
                self.assertEqual(self.window.clean_name(name), name)

    def test_missing_episode_title_preserves_original_name(self):
        name = "[Group] S01E03.mkv"
        self.assertEqual(self.window.clean_name(name), name)

    def test_underscored_episode_and_attached_version(self):
        for name, expected in [
            ("Show_Ep03_1080p.mkv", "Show 1080p - 03.mkv"),
            ("Show S01E03v2.mkv", "Show - S01 - 03.mkv"),
            ("Show - 04v3.mkv", "Show - 04.mkv"),
        ]:
            with self.subTest(name=name):
                self.assertEqual(self.window.clean_name(name), expected)

    def test_readme_examples(self):
        examples = [
            ("[Judas] Chained Soldier - S02E06.mkv", "Chained Soldier - S02 - 06.mkv"),
            ("Jujutsu Kaisen S01E03.mkv", "Jujutsu Kaisen - S01 - 03.mkv"),
            ("[SubsPlease] Yuusha no Kuzu - 06 (1080p).mkv", "Yuusha no Kuzu - 06.mkv"),
            ("One_Piece_-_1092_[1080p].mkv", "One Piece - 1092.mkv"),
            ("Spirited Away (2001).mkv", "Spirited Away.mkv"),
        ]
        for source, target in examples:
            with self.subTest(source=source):
                self.assertEqual(self.window.clean_name(source), target)

    def test_corrupt_settings_do_not_crash_startup(self):
        self.window.settings.setValue("geometry", "invalid geometry")
        self.window.settings.setValue("last_dir", [1, 2, 3])
        self.window.settings.setValue("autoload_last_dir", True)
        self.window.load_settings()
        self.assertEqual(self.window.last_directory(), "")

    def test_drop_deduplicates_paths_and_ignores_web_urls(self):
        source = self.video("Show.mkv")
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(source), QUrl.fromLocalFile(source),
                      QUrl("https://example.com/video.mkv")])
        event = QDropEvent(QPointF(0, 0), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        self.window.dropEvent(event)
        self.assertEqual([renamer.path_key(f) for f in self.window.files], [renamer.path_key(source)])

    def test_delete_only_removes_from_batch(self):
        source = self.video("Show.mkv")
        self.batch(source)
        self.window.table.selectRow(0)
        QTest.keyClick(self.window.table, Qt.Key_Delete)
        self.assertEqual(self.window.files, [])
        self.assertTrue(Path(source).exists())


if __name__ == "__main__":
    unittest.main()
