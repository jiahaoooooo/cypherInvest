import argparse
import json
import os
from urllib.parse import quote

from backend.save import SQLiteDatabase


DEFAULT_OVERRIDES_FILE = "logo_identity_overrides.json"
BRANDFETCH_BASE_URL = "https://cdn.brandfetch.io"


def build_brandfetch_logo_url(client_id, identifier_type, identifier_value):
    safe_value = quote(str(identifier_value).strip(), safe="")
    safe_client_id = quote(str(client_id).strip(), safe="")
    return f"{BRANDFETCH_BASE_URL}/{identifier_type}/{safe_value}?c={safe_client_id}"


def load_overrides(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def build_identity_record(company_row, overrides):
    ticker, company, cusip = company_row
    override = overrides.get(ticker, {})

    if override.get("domain"):
        return {
            "ticker": ticker,
            "company": company,
            "cusip": cusip,
            "identifier_type": "domain",
            "identifier_value": override["domain"],
            "resolver": "override",
            "status": "ready",
            "notes": override.get("notes"),
        }

    return {
        "ticker": ticker,
        "company": company,
        "cusip": cusip,
        "identifier_type": "ticker",
        "identifier_value": ticker,
        "resolver": "ticker",
        "status": "ready",
        "notes": None,
    }


def sync_identity_records(database, overrides):
    for row in database.get_distinct_companies():
        database.upsert_company_identity(build_identity_record(row, overrides))


def should_skip_logo_url_sync(database, ticker):
    logo_record = database.get_company_logo(ticker)
    if not logo_record:
        return False
    return (
        logo_record.get("status") == "ok"
        and logo_record.get("source") == "brandfetch"
        and bool(logo_record.get("logo_url"))
    )


def parse_args():
    parser = argparse.ArgumentParser(description="同步公司 Brandfetch logo URL 到 SQLite")
    parser.add_argument("--db-path", default="db/ark_data.db")
    parser.add_argument("--overrides-file", default=DEFAULT_OVERRIDES_FILE)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="即使数据库已有 logo_url 也重新生成",
    )
    return parser.parse_args()


def sync_logo_urls(database, client_id, refresh=False, limit=None):
    identities = []
    for row in database.get_distinct_companies():
        identity = database.get_company_identity(row[0])
        if identity:
            identities.append(identity)

    if limit is not None:
        identities = identities[:limit]

    for identity in identities:
        ticker = identity["ticker"]

        if not refresh and should_skip_logo_url_sync(database, ticker):
            continue

        logo_url = build_brandfetch_logo_url(
            client_id,
            identity["identifier_type"],
            identity["identifier_value"],
        )
        database.upsert_company_logo(
            {
                "ticker": ticker,
                "company": identity.get("company"),
                "logo_url": logo_url,
                "logo_path": None,
                "source": "brandfetch",
                "status": "ok",
            }
        )
        print(f"✅ {ticker}: logo url synced")


def main():
    args = parse_args()
    client_id = os.getenv("BRANDFETCH_CLIENT_ID")

    if not client_id:
        raise SystemExit("缺少环境变量 BRANDFETCH_CLIENT_ID，无法生成 logo URL。")

    database = SQLiteDatabase(args.db_path)
    overrides = load_overrides(args.overrides_file)
    sync_identity_records(database, overrides)
    sync_logo_urls(
        database,
        client_id=client_id,
        refresh=args.refresh,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
