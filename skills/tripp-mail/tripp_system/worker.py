"""Lease-fenced delivery workers from the v8.5 production design."""

from __future__ import annotations

import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .audit import AuditService
from .database import Database, execute_with_retry, is_expired, now_utc
from .delivery import PermanentError


class TransientError(Exception):
    """A delivery can safely be retried."""


class SystemHaltError(Exception):
    """Processing must stop because a fail-closed operation failed."""


class Worker:
    def __init__(self, agent_id: str, audit: AuditService, delivery_adapter: Any):
        self.agent_id = agent_id
        self.audit = audit
        self.delivery_adapter = delivery_adapter
        self.retry_count = 0
        self.last_heartbeat = time.time()
        self._stop = threading.Event()

    def process_one(self) -> bool:
        delivery = self.claim()
        if not delivery:
            return False
        try:
            self.deliver(delivery)
        except PermanentError:
            self.quarantine(delivery)
        except TransientError as exc:
            self.retry(delivery, str(exc))
        return True

    def claim(self) -> Optional[dict[str, Any]]:
        try:
            db = Database.begin()
            delivery = db.execute(
                """SELECT d.*, m.type, m.body, m.sender, m.chain_id,
                          m.chain_step, m.chain_total
                   FROM message_deliveries d JOIN messages m ON d.message_id=m.id
                   WHERE d.state IN ('pending','retry_scheduled')
                     AND d.recipient_id=?
                     AND (d.next_attempt_at IS NULL OR d.next_attempt_at<=?)
                     AND (m.expires_at IS NULL OR m.expires_at>?)
                     AND m.state NOT IN ('expired','cancelled')
                   ORDER BY m.priority DESC, m.priority_aging DESC, m.created_at ASC
                   LIMIT 1""",
                (self.agent_id, now_utc(), now_utc()),
            ).fetchone()
            if not delivery:
                Database.rollback()
                return None
            token = secrets.token_hex(16)
            execute_with_retry(
                db,
                """UPDATE message_deliveries
                   SET state='claimed', claimed_by=?, claimed_at=?,
                       lease_expires_at=datetime(?,'+5 minutes'),
                       lease_fencing_token=?
                   WHERE id=? AND state IN ('pending','retry_scheduled')""",
                (self.agent_id, now_utc(), now_utc(), token, delivery["id"]),
            )
            if db.execute("SELECT changes()").fetchone()[0] == 0:
                Database.rollback()
                return None
            self.audit.append(delivery["message_id"], delivery["id"], "claimed",
                              self.agent_id, {"token": token}, db)
            Database.commit()
            result = dict(delivery)
            result["lease_fencing_token"] = token
            return result
        except Exception:
            Database.rollback()
            raise

    def deliver(self, delivery: dict[str, Any]) -> None:
        operation_key = f"{delivery['message_id']}:{delivery['id']}"
        try:
            self.delivery_adapter(delivery, operation_key)
        except PermanentError:
            raise
        except (TimeoutError, ConnectionError, OSError) as exc:
            raise TransientError(str(exc)) from exc

        try:
            db = Database.begin()
            current = db.execute(
                "SELECT state,lease_fencing_token,lease_expires_at "
                "FROM message_deliveries WHERE id=?", (delivery["id"],)
            ).fetchone()
            if not current or current["state"] != "claimed" or current["lease_fencing_token"] != delivery["lease_fencing_token"]:
                Database.rollback()
                return
            if is_expired(current["lease_expires_at"]):
                Database.rollback()
                raise TransientError("Lease expired")
            parent = db.execute("SELECT state FROM messages WHERE id=?", (delivery["message_id"],)).fetchone()
            if parent and parent["state"] in ("cancelled", "expired"):
                db.execute(
                    "UPDATE message_deliveries SET state='expired',last_error=? "
                    "WHERE id=? AND state='claimed' AND lease_fencing_token=?",
                    ("Parent message cancelled", delivery["id"], delivery["lease_fencing_token"]),
                )
                Database.commit()
                return
            execute_with_retry(
                db,
                "UPDATE message_deliveries SET state='delivered',delivered_at=? "
                "WHERE id=? AND state='claimed' AND lease_fencing_token=?",
                (now_utc(), delivery["id"], delivery["lease_fencing_token"]),
            )
            if db.execute("SELECT changes()").fetchone()[0] == 0:
                Database.rollback()
                return
            self.audit.append(delivery["message_id"], delivery["id"], "delivered",
                              self.agent_id, {"to": delivery["recipient_id"]}, db)
            Database.commit()
        except Exception:
            Database.rollback()
            raise

    def retry(self, delivery: dict[str, Any], error: str) -> None:
        retry_count = delivery["retry_count"] + 1
        if retry_count >= delivery["max_retries"] or (
            delivery.get("retry_deadline") and is_expired(delivery["retry_deadline"])
        ):
            self.quarantine(delivery)
            return
        backoff = min(300, 2 * (2 ** (retry_count - 1)))
        next_at = (datetime.now(timezone.utc) + timedelta(seconds=backoff)).strftime("%Y-%m-%d %H:%M:%S")
        try:
            db = Database.begin()
            execute_with_retry(
                db,
                """UPDATE message_deliveries
                   SET state='retry_scheduled',retry_count=?,last_error=?,next_attempt_at=?,
                       lease_fencing_token=NULL,claimed_by=NULL,claimed_at=NULL,lease_expires_at=NULL
                   WHERE id=? AND state='claimed' AND lease_fencing_token=?""",
                (retry_count, error, next_at, delivery["id"], delivery["lease_fencing_token"]),
            )
            if db.execute("SELECT changes()").fetchone()[0] == 0:
                Database.rollback()
                return
            self.audit.append(delivery["message_id"], delivery["id"], "retry_scheduled",
                              self.agent_id, {"rc": retry_count, "next": next_at}, db)
            Database.commit()
        except Exception:
            Database.rollback()
            raise

    def quarantine(self, delivery: dict[str, Any]) -> None:
        try:
            db = Database.begin()
            execute_with_retry(
                db,
                "UPDATE message_deliveries SET state='failed',last_error='quarantine' "
                "WHERE id=? AND state='claimed' AND lease_fencing_token=?",
                (delivery["id"], delivery["lease_fencing_token"]),
            )
            if db.execute("SELECT changes()").fetchone()[0] == 0:
                Database.rollback()
                return
            self.audit.append(delivery["message_id"], delivery["id"], "failed", self.agent_id, {}, db)
            execute_with_retry(db, "UPDATE message_deliveries SET state='dead_lettered' WHERE id=? AND state='failed'", (delivery["id"],))
            self.audit.append(delivery["message_id"], delivery["id"], "dead_lettered", self.agent_id, {}, db)
            Database.commit()
        except Exception:
            Database.rollback()
            raise

    def stop(self) -> None:
        self._stop.set()


class WorkerSupervisor:
    def __init__(self) -> None:
        self.workers: dict[str, Worker] = {}
        self._shutdown = threading.Event()
        self._threads: dict[str, threading.Thread] = {}

    def register(self, worker_id: str, worker: Worker) -> None:
        self.workers[worker_id] = worker

    def start(self) -> None:
        for worker_id, worker in self.workers.items():
            thread = threading.Thread(target=self._run, args=(worker_id, worker), daemon=False)
            thread.start()
            self._threads[worker_id] = thread

    def _run(self, worker_id: str, worker: Worker) -> None:
        backoff = 1
        while not self._shutdown.is_set():
            try:
                processed = worker.process_one()
                worker.last_heartbeat = time.time()
                backoff = 1
                if not processed:
                    self._shutdown.wait(0.1)
            except Exception as exc:
                print(f"Worker {worker_id} crashed: {exc}. Restarting in {backoff}s...")
                Database.close()
                if self._shutdown.wait(backoff):
                    return
                backoff = min(backoff * 2, 60)
        Database.close()

    def shutdown(self) -> None:
        self._shutdown.set()
        for worker in self.workers.values():
            worker.stop()
        for thread in self._threads.values():
            thread.join(timeout=10)
        Database.close()


class MessageProcessor:
    """Minimal fail-closed processor retained from the approved design."""

    def __init__(self, audit: AuditService):
        self.audit = audit

    def process(self, message_id: str, delivery_id: int, worker_id: str) -> None:
        try:
            self.audit.append(message_id, delivery_id, "claimed", worker_id, {}, Database.get_connection())
        except Exception as exc:
            raise SystemHaltError(f"Audit failure — halted: {exc}") from exc
