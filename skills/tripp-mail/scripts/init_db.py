"""Initialize a TRIPP.SYSTEM SQLite database."""
import argparse
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    path = args.database.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = Path(__file__).parents[1] / "tripp_system" / "schema.sql"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(schema.read_text(encoding="utf-8"))
    print(f"Initialized {path}")


if __name__ == "__main__":
    main()

