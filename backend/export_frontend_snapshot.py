import argparse
import json
import sqlite3
from collections import defaultdict
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


def fetch_latest_snapshot(db_path: str) -> dict[str, Any]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row

        latest_date_row = connection.execute(
            "SELECT MAX(date) AS latest_date FROM holdings",
        ).fetchone()
        latest_date = latest_date_row["latest_date"] if latest_date_row else None

        if not latest_date:
            return {
                "snapshot_date": None,
                "previous_snapshot_date": None,
                "holdings": [],
            }

        previous_date_row = connection.execute(
            """
            SELECT MAX(date) AS previous_date
            FROM holdings
            WHERE date < ?
            """,
            (latest_date,),
        ).fetchone()
        previous_date = previous_date_row["previous_date"] if previous_date_row else None

        rows = connection.execute(
            """
            SELECT
                current.fund,
                current.ticker,
                current.company,
                CAST(current.weight AS REAL) * 100.0 AS weight,
                current.shares,
                CAST(current.market_value AS REAL) AS market_value,
                CASE
                    WHEN previous.weight IS NULL THEN NULL
                    ELSE (CAST(current.weight AS REAL) - CAST(previous.weight AS REAL)) * 100.0
                END AS weight_delta,
                CASE
                    WHEN previous.shares IS NULL THEN NULL
                    ELSE current.shares - previous.shares
                END AS shares_delta,
                CASE
                    WHEN previous.market_value IS NULL THEN NULL
                    ELSE CAST(current.market_value AS REAL) - CAST(previous.market_value AS REAL)
                END AS market_value_delta
            FROM holdings AS current
            LEFT JOIN holdings AS previous
                ON current.fund = previous.fund
               AND COALESCE(current.ticker, '') = COALESCE(previous.ticker, '')
               AND current.company = previous.company
               AND previous.date = ?
            WHERE current.date = ?
            ORDER BY current.fund ASC, CAST(current.weight AS REAL) DESC, current.company ASC
            """,
            (previous_date, latest_date),
        ).fetchall()

        previous_rows = []
        if previous_date:
            previous_rows = connection.execute(
                """
                SELECT
                    fund,
                    ticker,
                    company,
                    shares,
                    CAST(market_value AS REAL) AS market_value
                FROM holdings
                WHERE date = ?
                """,
                (previous_date,),
            ).fetchall()

    current_summary_by_fund: dict[str, dict[str, float]] = defaultdict(
        lambda: {"holdings_count": 0, "total_shares": 0, "total_market_value": 0.0},
    )
    for row in rows:
        current_summary = current_summary_by_fund[row["fund"]]
        current_summary["holdings_count"] += 1
        current_summary["total_shares"] += int(row["shares"] or 0)
        current_summary["total_market_value"] += float(row["market_value"] or 0.0)

    previous_summary_by_fund: dict[str, dict[str, float]] = defaultdict(
        lambda: {"holdings_count": 0, "total_shares": 0, "total_market_value": 0.0},
    )
    for row in previous_rows:
        previous_summary = previous_summary_by_fund[row["fund"]]
        previous_summary["holdings_count"] += 1
        previous_summary["total_shares"] += int(row["shares"] or 0)
        previous_summary["total_market_value"] += float(row["market_value"] or 0.0)

    fund_summaries = {
        fund: {
            "holdings_count": int(current["holdings_count"]),
            "holdings_count_delta": (
                int(current["holdings_count"] - previous_summary_by_fund[fund]["holdings_count"])
                if previous_date
                else None
            ),
            "total_shares": int(current["total_shares"]),
            "total_shares_delta": (
                int(current["total_shares"] - previous_summary_by_fund[fund]["total_shares"])
                if previous_date
                else None
            ),
            "total_market_value": round(float(current["total_market_value"]), 4),
            "total_market_value_delta": (
                round(
                    float(
                        current["total_market_value"]
                        - previous_summary_by_fund[fund]["total_market_value"]
                    ),
                    4,
                )
                if previous_date
                else None
            ),
        }
        for fund, current in current_summary_by_fund.items()
    }

    return {
        "snapshot_date": latest_date,
        "previous_snapshot_date": previous_date,
        "fund_summaries": fund_summaries,
        "holdings": [
            {
                "fund": row["fund"],
                "ticker": row["ticker"] or "",
                "company": row["company"],
                "weight": round(float(row["weight"]), 4),
                "shares": int(row["shares"] or 0),
                "market_value": round(float(row["market_value"]), 4),
                "weight_delta": (
                    round(float(row["weight_delta"]), 4)
                    if row["weight_delta"] is not None
                    else None
                ),
                "shares_delta": (
                    int(row["shares_delta"])
                    if row["shares_delta"] is not None
                    else None
                ),
                "market_value_delta": (
                    round(float(row["market_value_delta"]), 4)
                    if row["market_value_delta"] is not None
                    else None
                ),
            }
            for row in rows
        ],
    }


def write_snapshot(snapshot: dict[str, Any], output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    snapshot = fetch_latest_snapshot(args.db_path)
    write_snapshot(snapshot, args.output)
    print(
        f"Exported {len(snapshot['holdings'])} rows for "
        f"{snapshot['snapshot_date']} to {args.output}",
    )


if __name__ == "__main__":
    main()
