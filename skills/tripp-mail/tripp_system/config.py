"""Validated runtime configuration."""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True, slots=True)
class Configuration:
    db_path: str
    lease_minutes: int = 5
    reaper_batch_size: int = 100
    reaper_interval_seconds: int = 30
    sqlite_busy_timeout_ms: int = 5000
    wal_autocheckpoint_pages: int = 1000


def load_config(environ: Mapping[str, str] | None = None) -> Configuration:
    env = os.environ if environ is None else environ
    default_path = str((Path.cwd() / "tripp-system.db").resolve())

    def positive(name: str, default: int) -> int:
        value = int(env.get(name, str(default)))
        if value <= 0:
            raise ValueError(f"{name} must be positive")
        return value

    return Configuration(
        db_path=env.get("TRIPP_DB_PATH", default_path),
        lease_minutes=positive("TRIPP_LEASE_MINUTES", 5),
        reaper_batch_size=positive("TRIPP_REAPER_BATCH_SIZE", 100),
        reaper_interval_seconds=positive("TRIPP_REAPER_INTERVAL_SECONDS", 30),
        sqlite_busy_timeout_ms=positive("TRIPP_SQLITE_BUSY_TIMEOUT_MS", 5000),
        wal_autocheckpoint_pages=positive("TRIPP_WAL_AUTOCHECKPOINT_PAGES", 1000),
    )
