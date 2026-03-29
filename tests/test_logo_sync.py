import tempfile
import unittest
from pathlib import Path

from backend.save import SQLiteDatabase
from backend.sync_logos import (
    build_brandfetch_logo_url,
    should_skip_logo_url_sync,
    sync_identity_records,
    sync_logo_urls,
)


class LogoSyncTests(unittest.TestCase):
    def test_build_brandfetch_logo_url_for_ticker(self):
        url = build_brandfetch_logo_url("client123", "ticker", "AAPL")

        self.assertEqual(
            url,
            "https://cdn.brandfetch.io/ticker/AAPL?c=client123",
        )

    def test_sync_identity_records_uses_override_domain(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "logos.db"
            database = SQLiteDatabase(str(db_path))
            database.save_records(
                [
                    (
                        "2026-03-27",
                        "ARKK",
                        "TESLA INC",
                        "TSLA",
                        "88160R101",
                        100,
                        "1000",
                        "0.1",
                    )
                ]
            )

            sync_identity_records(
                database,
                overrides={"TSLA": {"domain": "tesla.com"}},
            )

            identity = database.get_company_identity("TSLA")
            self.assertEqual(identity["identifier_type"], "domain")
            self.assertEqual(identity["identifier_value"], "tesla.com")
            self.assertEqual(identity["status"], "ready")

    def test_should_skip_logo_url_sync_when_ok_record_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "logos.db"
            database = SQLiteDatabase(str(db_path))
            database.upsert_company_logo(
                {
                    "ticker": "TSLA",
                    "company": "TESLA INC",
                    "logo_url": "https://example.com/logo.png",
                    "logo_path": None,
                    "source": "brandfetch",
                    "status": "ok",
                }
            )

            self.assertTrue(should_skip_logo_url_sync(database, "TSLA"))

    def test_should_not_skip_logo_url_sync_for_non_brandfetch_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "logos.db"
            database = SQLiteDatabase(str(db_path))
            database.upsert_company_logo(
                {
                    "ticker": "TSLA",
                    "company": "TESLA INC",
                    "logo_url": "https://example.com/logo.png",
                    "logo_path": None,
                    "source": "logo.dev",
                    "status": "ok",
                }
            )

            self.assertFalse(should_skip_logo_url_sync(database, "TSLA"))

    def test_sync_logo_urls_updates_database_without_downloading_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "logos.db"
            database = SQLiteDatabase(str(db_path))
            database.save_records(
                [
                    (
                        "2026-03-27",
                        "ARKK",
                        "APPLE INC",
                        "AAPL",
                        "037833100",
                        100,
                        "1000",
                        "0.1",
                    )
                ]
            )

            sync_identity_records(database, overrides={})
            sync_logo_urls(database, client_id="token123")

            logo = database.get_company_logo("AAPL")
            self.assertEqual(logo["status"], "ok")
            self.assertEqual(logo["source"], "brandfetch")
            self.assertEqual(
                logo["logo_url"],
                "https://cdn.brandfetch.io/ticker/AAPL?c=token123",
            )
            self.assertIsNone(logo["logo_path"])


if __name__ == "__main__":
    unittest.main()
