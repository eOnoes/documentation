import hashlib
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
def is_expired(ts: str) -> bool:
    if not ts:
        return False
    parsed = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    return parsed < datetime.now(timezone.utc)
def compute_content_hash(msg: Dict[str, Any]) -> str:
    """Deterministic SHA-256 of message content fields only."""
    content = {
        "id": msg["id"], "type": msg["type"], "sender": msg["sender"],
        "recipient": msg["recipient"], "subject": msg.get("subject", ""),
        "body": msg["body"], "chain_id": msg.get("chain_id", ""),
        "chain_step": msg.get("chain_step", 0), "chain_total": msg.get("chain_total", 1),
    }
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
class Database:
    """Thread-safe SQLite with connection-per-thread and ownership validation."""
    _local = threading.local()
    _db_path: Optional[str] = None

    @classmethod
    def configure(cls, db_path: str):
        """Configure one native absolute path before any worker threads start."""
        if os.name == 'nt' and db_path.startswith('/'):
            raise ValueError("Use a native Windows path (for example C:\\data\\tripp.db), not an MSYS path")
        path = Path(os.path.expandvars(os.path.expanduser(db_path)))
        if not path.is_absolute():
            raise ValueError("TRIPP_DB_PATH must be an absolute native-OS path")
        path.parent.mkdir(parents=True, exist_ok=True)
        cls._db_path = str(path)

    @classmethod
    def get_connection(cls) -> sqlite3.Connection:
        if cls._db_path is None:
            raise RuntimeError("Database.configure(TRIPP_DB_PATH) must run before use")
        tid = threading.get_ident()
        if hasattr(cls._local, 'conn') and cls._local.conn is not None:
            if cls._local.thread_id != tid:
                raise RuntimeError(
                    f"Thread ownership violation: conn owned by {cls._local.thread_id}, "
                    f"accessed by {tid}"
                )
            return cls._local.conn
        conn = sqlite3.connect(cls._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        if mode.lower() != 'wal':
            conn.close()
            raise RuntimeError(f"WAL unavailable for {cls._db_path!r}: got {mode!r}")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA wal_autocheckpoint=1000")
        cls._local.conn = conn
        cls._local.thread_id = tid
        return conn

    @classmethod
    def initialize(cls) -> sqlite3.Connection:
        """Apply the packaged schema to an empty database and validate existing ones."""
        conn = cls.get_connection()
        has_schema = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        if not has_schema:
            schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
            conn.executescript(schema)
            conn.commit()
        version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        if version != 4:
            raise RuntimeError(f"Unsupported schema version: {version!r}")
        return conn

    @classmethod
    def close(cls):
        if hasattr(cls._local, 'conn') and cls._local.conn:
            cls._local.conn.close()
            cls._local.conn = None
            cls._local.thread_id = None

    @classmethod
    def begin(cls):
        c = cls.get_connection()
        c.execute("BEGIN IMMEDIATE")
        return c

    @classmethod
    def commit(cls):
        cls.get_connection().commit()

    @classmethod
    def rollback(cls):
        # rollback() is also used from exception paths before configure succeeds.
        if cls._db_path is not None:
            cls.get_connection().rollback()
def execute_with_retry(db, query, params, retries=3):
    for i in range(retries):
        try:
            return db.execute(query, params)
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and i < retries - 1:
                time.sleep(0.05 * (i + 1))
            else:
                raise
