#!/usr/bin/env python3
"""Pure contracts for the stage table: row tooltips, which path a double-click opens, and the fitted height."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from shared import ui_run_status_panel as panel


class FakeItem:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class FakeTable:
    def __init__(self, rows: list[list[str]]) -> None:
        self.rows = rows

    def item(self, row: int, column: int):
        return FakeItem(self.rows[row][column])


class RowPathsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def touch(self, name: str) -> str:
        path = self.root / name
        path.write_text("x", encoding="utf-8")
        return path.as_posix()

    def test_tooltip_lists_only_the_non_empty_paths_one_per_line(self) -> None:
        self.assertEqual(
            panel.row_path_tooltip("/m.json", "", "/logs"), "Manifest: /m.json\nLogs: /logs"
        )
        self.assertEqual(
            panel.row_path_tooltip("/m.json", "/qc.json", "/logs"), "Manifest: /m.json\nQC: /qc.json\nLogs: /logs"
        )
        self.assertEqual(panel.row_path_tooltip("", "", ""), "")

    def test_first_existing_path_prefers_qc_then_logs_then_manifest(self) -> None:
        qc, logs, manifest = self.touch("qc.json"), self.touch("logs.txt"), self.touch("m.json")
        self.assertEqual(panel.first_existing_path(qc, logs, manifest), Path(qc))
        self.assertEqual(panel.first_existing_path(self.root.joinpath("gone").as_posix(), logs, manifest), Path(logs))
        gone = self.root.joinpath("gone").as_posix()
        self.assertEqual(panel.first_existing_path(gone, "", manifest), Path(manifest))
        self.assertIsNone(panel.first_existing_path(gone, "", ""))

    def test_row_open_path_reads_the_hidden_columns_of_any_clicked_row(self) -> None:
        qc, manifest = self.touch("qc.json"), self.touch("m.json")
        table = FakeTable([["target", "state", "reason", manifest, qc, ""], ["t2", "s", "r", "", "", ""]])
        self.assertEqual(panel.row_open_path(table, 0), Path(qc))
        self.assertIsNone(panel.row_open_path(table, 1))

    def test_module_widget_double_click_uses_the_row_helper_for_every_column(self) -> None:
        source = (Path(__file__).resolve().parents[2] / "shared" / "module_widget.py").read_text(encoding="utf-8")
        start = source.index("def _on_run_status_table_double_clicked")
        body = source[start:source.index("    def ", start + 10)]
        self.assertIn("row_open_path(", body)
        self.assertNotIn("column < 3", body)


class TableHeightTest(unittest.TestCase):
    def test_height_is_header_plus_rows_plus_frame_with_rows_clamped_to_one_to_eight(self) -> None:
        self.assertEqual(panel.table_height(4, 24, 22, 1), 24 + 4 * 22 + 2)
        self.assertEqual(panel.table_height(0, 24, 22, 1), 24 + 1 * 22 + 2)
        self.assertEqual(panel.table_height(20, 24, 22, 1), 24 + 8 * 22 + 2)

    def test_fit_table_height_reads_the_table_and_fixes_its_height(self) -> None:
        table = mock.MagicMock()
        table.rowCount = 3  # PythonQt exposes counts as properties
        table.horizontalHeader.return_value.sizeHint.return_value.height.return_value = 24
        table.verticalHeader.return_value.defaultSectionSize = 22
        table.frameWidth = 1
        panel.fit_table_height(table)
        table.setFixedHeight.assert_called_once_with(24 + 3 * 22 + 2)


class SetRowsTest(unittest.TestCase):
    def test_target_cell_carries_the_paths_and_rows_are_not_resized_to_contents(self) -> None:
        qt = mock.MagicMock()
        qt.QTableWidgetItem.side_effect = lambda text="": mock.MagicMock(name=f"item:{text}", cell_text=text)
        table = mock.MagicMock()
        table.rowCount = 1
        table.horizontalHeader.return_value.sizeHint.return_value.height.return_value = 24
        table.verticalHeader.return_value.defaultSectionSize = 22
        table.frameWidth = 1
        widget = SimpleNamespace(_runStatusTable=table)
        rows = [{"target": "segmentation", "status": "completed", "reason": "outputs found",
                 "manifest_path": "/m.json", "qc_path": "/qc.json", "logs_dir": ""}]
        with mock.patch.dict(sys.modules, {"qt": qt}):
            panel.set_run_status_table_rows(widget, rows)

        placed = {call[0][1]: call[0][2] for call in table.setItem.call_args_list}
        self.assertEqual(placed[0].setToolTip.call_args[0][0], "Manifest: /m.json\nQC: /qc.json")
        self.assertEqual(placed[2].cell_text, "outputs found")
        self.assertEqual(placed[3].cell_text, "/m.json")  # hidden columns keep their items
        table.resizeRowsToContents.assert_not_called()
        table.setFixedHeight.assert_called_with(24 + 22 + 2)


if __name__ == "__main__":
    unittest.main()
