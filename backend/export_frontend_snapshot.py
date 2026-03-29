import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export the latest ARK holdings snapshot for the frontend.",
    )
    parser.add_argument(
        "--db-path",
        default="db/ark_data.db",
        help="SQLite database path. Defaults to db/ark_data.db.",
    )
    parser.add_argument(
        "--output",
        default="frontend/ark-holdings-latest.json",
        help="Frontend snapshot output path.",
    )
    return parser.parse_args()


def fetch_latest_rows(db_path: str) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row

        latest_date_row = connection.execute(
            "SELECT MAX(date) AS latest_date FROM holdings",
        ).fetchone()
        latest_date = latest_date_row["latest_date"] if latest_date_row else None

        if not latest_date:
            return []

        rows = connection.execute(
            """
            SELECT
                fund,
                ticker,
                company,
                CAST(weight AS REAL) * 100.0 AS weight,
                shares,
                CAST(market_value AS REAL) AS market_value
            FROM holdings
            WHERE date = ?
            ORDER BY fund ASC, CAST(weight AS REAL) DESC, company ASC
            """,
            (latest_date,),
        ).fetchall()

    return [
        {
            "fund": row["fund"],
            "ticker": row["ticker"] or "",
            "company": row["company"],
            "weight": round(float(row["weight"]), 4),
            "shares": int(row["shares"] or 0),
            "market_value": round(float(row["market_value"]), 4),
        }
        for row in rows
    ]


def write_snapshot(rows: list[dict[str, Any]], output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    rows = fetch_latest_rows(args.db_path)
    write_snapshot(rows, args.output)
    print(f"Exported {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
