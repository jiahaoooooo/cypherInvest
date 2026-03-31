import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.export_frontend_snapshot import fetch_latest_snapshot


SCHEMA_SQL = """
CREATE TABLE holdings (
    date TEXT NOT NULL,
    fund TEXT NOT NULL,
    ticker TEXT,
    company TEXT NOT NULL,
    weight REAL NOT NULL,
    shares INTEGER NOT NULL,
    market_value REAL NOT NULL
)
"""


class ExportFrontendSnapshotTests(unittest.TestCase):
    def _build_db(self) -> Path:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        db_path = Path(tmpdir.name) / "ark.db"
        with sqlite3.connect(db_path) as connection:
            connection.execute(SCHEMA_SQL)
            connection.executemany(
                """
                INSERT INTO holdings (date, fund, ticker, company, weight, shares, market_value)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("2026-03-26", "ARKK", "TSLA", "TESLA INC", 0.10, 100, 1000.0),
                    ("2026-03-26", "ARKK", "ROKU", "ROKU INC", 0.05, 50, 500.0),
                    ("2026-03-27", "ARKK", "TSLA", "TESLA INC", 0.12, 120, 1260.0),
                    ("2026-03-27", "ARKK", "ROKU", "ROKU INC", 0.04, 40, 420.0),
                    ("2026-03-27", "ARKK", "SHOP", "SHOPIFY INC", 0.03, 10, 300.0),
                ],
            )
        return db_path

    def test_fetch_latest_snapshot_includes_previous_snapshot_date(self) -> None:
        db_path = self._build_db()

        snapshot = fetch_latest_snapshot(str(db_path))

        self.assertEqual(snapshot["snapshot_date"], "2026-03-27")
        self.assertEqual(snapshot["previous_snapshot_date"], "2026-03-26")

    def test_fetch_latest_snapshot_calculates_deltas_against_previous_day(self) -> None:
        db_path = self._build_db()

        snapshot = fetch_latest_snapshot(str(db_path))
        holdings = {item["ticker"]: item for item in snapshot["holdings"]}
        fund_summary = snapshot["fund_summaries"]["ARKK"]

        self.assertEqual(holdings["TSLA"]["weight_delta"], 2.0)
        self.assertEqual(holdings["TSLA"]["shares_delta"], 20)
        self.assertEqual(holdings["TSLA"]["market_value_delta"], 260.0)

        self.assertEqual(holdings["ROKU"]["weight_delta"], -1.0)
        self.assertEqual(holdings["ROKU"]["shares_delta"], -10)
        self.assertEqual(holdings["ROKU"]["market_value_delta"], -80.0)
        self.assertEqual(fund_summary["holdings_count_delta"], 1)
        self.assertEqual(fund_summary["total_shares_delta"], 20)
        self.assertEqual(fund_summary["total_market_value_delta"], 480.0)

    def test_fetch_latest_snapshot_uses_none_for_new_holding_without_previous_day(self) -> None:
        db_path = self._build_db()

        snapshot = fetch_latest_snapshot(str(db_path))
        shop = next(item for item in snapshot["holdings"] if item["ticker"] == "SHOP")

        self.assertIsNone(shop["weight_delta"])
        self.assertIsNone(shop["shares_delta"])
        self.assertIsNone(shop["market_value_delta"])


if __name__ == "__main__":
    unittest.main()
