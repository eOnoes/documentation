"""Append-only, signed audit hash chain."""

import hashlib
import hmac
import json
import sqlite3
import threading
from typing import Any

from .database import now_utc


class AuditService:
    def __init__(self, hmac_keys: dict[str, bytes]):
        self.hmac_keys = hmac_keys
        self._seq_lock = threading.Lock()

    def append(self, message_id: str | None, delivery_id: int | None, action: str,
               actor: str, details: dict[str, Any], db: sqlite3.Connection) -> None:
        timestamp = now_utc()
        with self._seq_lock:
            seq = db.execute(
                "UPDATE audit_sequence SET last_value=last_value+1 RETURNING last_value"
            ).fetchone()[0]
            event_id = f"{actor}:{action}:{message_id}:{delivery_id or ''}:{timestamp}:{seq}"
            previous = db.execute("SELECT record_hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
            previous_hash = previous[0] if previous else "0" * 64
            record = {
                "event_id": event_id, "message_id": message_id, "delivery_id": delivery_id,
                "action": action, "actor": actor, "details": details,
                "timestamp": timestamp, "previous_hash": previous_hash,
            }
            canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
            record_hash = hashlib.sha256(canonical.encode()).hexdigest()
            if actor == "system":
                signature = None
            else:
                key = self.hmac_keys.get(actor)
                if key is None:
                    raise ValueError(f"No HMAC key for agent '{actor}' — cannot sign audit event")
                signature = hmac.new(key, f"{actor}:{canonical}".encode(), hashlib.sha256).hexdigest()
            db.execute(
                """INSERT INTO audit_log
                   (event_id,message_id,delivery_id,action,actor,details,timestamp,
                    previous_hash,record_hash,signature) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (event_id, message_id, delivery_id, action, actor, json.dumps(details),
                 timestamp, previous_hash, record_hash, signature),
            )

    def verify(self, db: sqlite3.Connection) -> bool:
        previous_hash = "0" * 64
        for row in db.execute("SELECT * FROM audit_log ORDER BY id").fetchall():
            if row["previous_hash"] != previous_hash:
                return False
            record = {
                "event_id": row["event_id"], "message_id": row["message_id"],
                "delivery_id": row["delivery_id"], "action": row["action"],
                "actor": row["actor"],
                "details": json.loads(row["details"]) if row["details"] else {},
                "timestamp": row["timestamp"], "previous_hash": row["previous_hash"],
            }
            canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
            if row["record_hash"] != hashlib.sha256(canonical.encode()).hexdigest():
                return False
            if row["actor"] != "system":
                key = self.hmac_keys.get(row["actor"])
                if key is None:
                    return False
                expected = hmac.new(key, f"{row['actor']}:{canonical}".encode(), hashlib.sha256).hexdigest()
                if not hmac.compare_digest(row["signature"] or "", expected):
                    return False
            previous_hash = row["record_hash"]
        return True
