"""Command-line entry point for database setup and audit verification."""

import argparse
import json
from collections.abc import Sequence

from .audit import AuditService
from .config import load_config
from .database import Database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tripp-system")
    parser.add_argument("--db", help="absolute native path (overrides TRIPP_DB_PATH)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="create or validate the v8.5 database")
    sub.add_parser("verify-audit", help="verify the audit hash chain (system records only without keys)")
    sub.add_parser("status", help="print queue state counts")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config()
    Database.configure(args.db or config.db_path)
    try:
        if args.command == "init-db":
            Database.initialize()
            return 0
        db = Database.get_connection()
        if args.command == "verify-audit":
            return 0 if AuditService({}).verify(db) else 1
        rows = db.execute("SELECT state,COUNT(*) AS count FROM messages GROUP BY state").fetchall()
        print(json.dumps({row["state"]: row["count"] for row in rows}, sort_keys=True))
        return 0
    finally:
        Database.close()


if __name__ == "__main__":
    raise SystemExit(main())
