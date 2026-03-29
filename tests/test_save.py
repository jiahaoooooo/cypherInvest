import tempfile
import unittest
from pathlib import Path

from backend.save import (
    find_latest_date_prefix,
    resolve_scan_date_prefix,
    should_skip_scan,
)


class FakeDatabase:
    def __init__(self, existing_dates=None):
        self.existing_dates = set(existing_dates or [])

    def has_records_for_date(self, date_str):
        return date_str in self.existing_dates


class SaveDateSelectionTests(unittest.TestCase):
    def test_find_latest_date_prefix_returns_latest_csv_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "ARKK").mkdir()
            (root / "ARKQ").mkdir()
            (root / "ARKK" / "2026-03-26_ARKK.csv").write_text("header\n", encoding="utf-8")
            (root / "ARKQ" / "2026-03-27_ARKQ.csv").write_text("header\n", encoding="utf-8")

            self.assertEqual(find_latest_date_prefix(root), "2026-03-27")

    def test_find_latest_date_prefix_ignores_invalid_file_names(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "ARKK").mkdir()
            (root / "ARKK" / "latest_ARKK.csv").write_text("header\n", encoding="utf-8")
            (root / "ARKK" / "2026_03_27_ARKK.csv").write_text("header\n", encoding="utf-8")

            self.assertIsNone(find_latest_date_prefix(root))

    def test_resolve_scan_date_prefix_prefers_explicit_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "ARKK").mkdir()
            (root / "ARKK" / "2026-03-27_ARKK.csv").write_text("header\n", encoding="utf-8")

            self.assertEqual(
                resolve_scan_date_prefix(root, date_prefix="2026-03-20", scan_all=False),
                "2026-03-20",
            )

    def test_resolve_scan_date_prefix_returns_none_for_all_scan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "ARKK").mkdir()
            (root / "ARKK" / "2026-03-27_ARKK.csv").write_text("header\n", encoding="utf-8")

            self.assertIsNone(resolve_scan_date_prefix(root, date_prefix=None, scan_all=True))

    def test_should_skip_scan_when_latest_date_already_exists(self):
        database = FakeDatabase(existing_dates={"2026-03-27"})

        self.assertTrue(should_skip_scan(database, "2026-03-27", scan_all=False))

    def test_should_not_skip_scan_when_latest_date_missing(self):
        database = FakeDatabase(existing_dates=set())

        self.assertFalse(should_skip_scan(database, "2026-03-27", scan_all=False))

    def test_should_not_skip_scan_for_full_backfill(self):
        database = FakeDatabase(existing_dates={"2026-03-27"})

        self.assertFalse(should_skip_scan(database, "2026-03-27", scan_all=True))


if __name__ == "__main__":
    unittest.main()
