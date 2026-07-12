"""Round 20 production-realism tests for the executable v8.4 design."""
from pathlib import Path
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import threading
import unittest


from tripp_system.audit_service import AuditService
from tripp_system.credential_service import CredentialService
from tripp_system.database import Database
from tripp_system.errors import PermanentError
from tripp_system.models import generate_message_id, validate_message_id
from tripp_system.reaper import LeaseReaper
from tripp_system.worker import Worker

SCHEMA = (Path(__file__).parents[1] / "tripp_system" / "schema.sql").read_text(encoding="utf-8")
PROD = {
    "AuditService": AuditService, "CredentialService": CredentialService,
    "Database": Database, "PermanentError": PermanentError,
    "generate_message_id": generate_message_id,
    "validate_message_id": validate_message_id,
    "LeaseReaper": LeaseReaper, "Worker": Worker,
}
def connect(path):
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    mode = db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    if mode.lower() != "wal":
        raise AssertionError(mode)
    return db


def insert_message(db, mid, recipient="echo", body="payload"):
    content_hash = hashlib.sha256(body.encode()).hexdigest()
    db.execute(
        "INSERT INTO messages(id,type,sender,recipient,body,content_hash) VALUES(?,?,?,?,?,?)",
        (mid, "message", "eddie", recipient, body, content_hash),
    )


class Round20ProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "tripp.db")
        self.db = connect(self.path)
        self.db.executescript(SCHEMA)

    def tearDown(self):
        try:
            PROD["Database"].close()
            PROD["Database"]._db_path = None
        finally:
            self.db.close()
            self.tmp.cleanup()

    def test_wal_is_file_backed_and_checkpointable(self):
        self.assertEqual(self.db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        insert_message(self.db, "wal-1")
        self.db.commit()
        result = self.db.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        self.assertEqual(result[0], 0)
        self.assertTrue(Path(self.path).is_file())

    def test_four_workers_claim_each_delivery_once(self):
        for i in range(240):
            insert_message(self.db, f"claim-{i}")
        self.db.commit()
        claimed = []
        lock = threading.Lock()

        def worker(number):
            db = connect(self.path)
            while True:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT id FROM message_deliveries WHERE state='pending' ORDER BY id LIMIT 1"
                ).fetchone()
                if row is None:
                    db.rollback()
                    break
                token = f"w{number}-{row['id']}"
                changed = db.execute(
                    "UPDATE message_deliveries SET state='claimed',claimed_by='echo',lease_fencing_token=? "
                    "WHERE id=? AND state='pending'", (token, row["id"])
                ).rowcount
                db.commit()
                if changed:
                    with lock:
                        claimed.append(row["id"])
            db.close()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(claimed), 240)
        self.assertEqual(len(set(claimed)), 240)

    def test_crash_mid_transaction_rolls_back_claim(self):
        insert_message(self.db, "crash-1")
        self.db.commit()
        db = connect(self.path)
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE message_deliveries SET state='claimed' WHERE message_id='crash-1'")
        db.close()  # process/worker loss before COMMIT
        state = self.db.execute(
            "SELECT state FROM message_deliveries WHERE message_id='crash-1'"
        ).fetchone()[0]
        self.assertEqual(state, "pending")

    def test_network_partition_schedules_retry_without_false_delivery(self):
        insert_message(self.db, "net-1")
        self.db.commit()
        self.db.close()
        PROD["Database"].configure(self.path)
        audit = PROD["AuditService"]({"echo": b"round20-key"})

        def partitioned_adapter(delivery, operation_key):
            raise TimeoutError("Tailscale peer unreachable")

        worker = PROD["Worker"]("echo", audit, partitioned_adapter)
        self.assertTrue(worker.process_one())
        PROD["Database"].close()
        self.db = connect(self.path)
        row = self.db.execute(
            "SELECT state,retry_count,delivered_at FROM message_deliveries WHERE message_id='net-1'"
        ).fetchone()
        self.assertEqual((row["state"], row["retry_count"], row["delivered_at"]),
                         ("retry_scheduled", 1, None))

    def test_successful_adapter_completes_without_post_commit_crash(self):
        insert_message(self.db, "success-1")
        self.db.commit()
        self.db.close()
        PROD["Database"].configure(self.path)
        audit = PROD["AuditService"]({"echo": b"round20-key"})
        calls = []

        def successful_adapter(delivery, operation_key):
            calls.append(operation_key)

        worker = PROD["Worker"]("echo", audit, successful_adapter)
        self.assertTrue(worker.process_one())
        self.assertEqual(len(calls), 1)
        row = PROD["Database"].get_connection().execute(
            "SELECT state,delivered_at FROM message_deliveries WHERE message_id='success-1'"
        ).fetchone()
        self.assertEqual(row["state"], "delivered")
        self.assertIsNotNone(row["delivered_at"])
        self.assertTrue(audit.verify(PROD["Database"].get_connection()))
        PROD["Database"].close()
        self.db = connect(self.path)

    def test_permanent_failure_dead_letters_without_post_commit_crash(self):
        insert_message(self.db, "permanent-1")
        self.db.commit()
        self.db.close()
        PROD["Database"].configure(self.path)
        audit = PROD["AuditService"]({"echo": b"round20-key"})

        def permanently_failing_adapter(delivery, operation_key):
            raise PROD["PermanentError"]("invalid destination")

        worker = PROD["Worker"]("echo", audit, permanently_failing_adapter)
        self.assertTrue(worker.process_one())
        row = PROD["Database"].get_connection().execute(
            "SELECT state,last_error FROM message_deliveries WHERE message_id='permanent-1'"
        ).fetchone()
        self.assertEqual((row["state"], row["last_error"]),
                         ("dead_lettered", "quarantine"))
        self.assertTrue(audit.verify(PROD["Database"].get_connection()))
        PROD["Database"].close()
        self.db = connect(self.path)

    def test_reaper_uses_bounded_batches_under_load(self):
        for i in range(250):
            insert_message(self.db, f"reap-{i}")
        self.db.execute(
            "UPDATE message_deliveries SET state='claimed',claimed_by='echo',"
            "lease_expires_at='2020-01-01 00:00:00',lease_fencing_token='old'"
        )
        self.db.commit()
        self.db.close()
        PROD["Database"].configure(self.path)
        reaper = PROD["LeaseReaper"](PROD["AuditService"]({}))
        self.assertEqual(reaper._reap_claim_batch(100), 100)
        self.assertEqual(reaper._reap_claim_batch(100), 100)
        self.assertEqual(reaper._reap_claim_batch(100), 50)
        self.assertEqual(reaper._reap_claim_batch(100), 0)
        PROD["Database"].close()
        self.db = connect(self.path)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM message_deliveries WHERE state='retry_scheduled'"
        ).fetchone()[0], 250)

    def test_broadcast_and_single_recipient_mix(self):
        for i in range(40):
            insert_message(self.db, f"single-{i}", "echo")
            insert_message(self.db, f"broadcast-{i}", "all")
        self.db.commit()
        singles = self.db.execute(
            "SELECT COUNT(*) FROM message_deliveries d JOIN messages m ON m.id=d.message_id "
            "WHERE m.recipient='echo'"
        ).fetchone()[0]
        broadcasts = self.db.execute(
            "SELECT COUNT(*) FROM message_deliveries d JOIN messages m ON m.id=d.message_id "
            "WHERE m.recipient='all'"
        ).fetchone()[0]
        self.assertEqual((singles, broadcasts), (40, 200))

    def test_audit_is_append_only_and_chain_verifies(self):
        self.db.close()
        PROD["Database"].configure(self.path)
        audit = PROD["AuditService"]({"echo": b"round20-key"})
        db = PROD["Database"].begin()
        audit.append(None, None, "health_changed", "echo", {"ok": True}, db)
        PROD["Database"].commit()
        self.assertTrue(audit.verify(PROD["Database"].get_connection()))
        with self.assertRaises(sqlite3.IntegrityError):
            PROD["Database"].get_connection().execute("UPDATE audit_log SET details='{}'")
        PROD["Database"].rollback()
        with self.assertRaises(sqlite3.IntegrityError):
            PROD["Database"].get_connection().execute("DELETE FROM audit_log")
        PROD["Database"].rollback()
        PROD["Database"].close()
        self.db = connect(self.path)

    def test_large_database_and_integrity_check(self):
        body = "x" * 100_000
        for i in range(120):
            insert_message(self.db, f"large-{i}", body=body)
        self.db.commit()
        self.assertGreater(Path(self.path).stat().st_size, 10_000_000)
        self.assertEqual(self.db.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_path_policy_is_explicit_and_platform_safe(self):
        configure = PROD["Database"].configure
        with self.assertRaises(ValueError):
            configure("relative/tripp.db")
        if os.name == "nt":
            with self.assertRaises(ValueError):
                configure("/c/Users/example/tripp.db")
        else:
            with self.assertRaises(ValueError):
                configure(r"C:\Users\example\tripp.db")


if __name__ == "__main__":
    unittest.main(verbosity=2)

