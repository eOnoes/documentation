import threading
from datetime import datetime, timezone, timedelta

from .audit_service import AuditService
from .database import Database, execute_with_retry, now_utc

class LeaseReaper:
    def __init__(self, audit: AuditService):
        self.audit = audit
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                self._expire_messages()
                self._reap_claims()
            except Exception as e:
                print(f"Reaper error: {e}")
            self._stop.wait(timeout=30)
        Database.close()

    def _expire_messages(self):
        """Atomically expire overdue active parents; cascade triggers revoke their deliveries."""
        try:
            db = Database.begin()
            overdue = db.execute(
                """SELECT id FROM messages
                   WHERE expires_at IS NOT NULL AND expires_at <= ?
                     AND state IN ('pending','claimed','retry_scheduled')""",
                (now_utc(),),
            ).fetchall()
            for message in overdue:
                db.execute(
                    """UPDATE messages SET state='expired'
                       WHERE id=? AND state IN ('pending','claimed','retry_scheduled')""",
                    (message['id'],),
                )
                if db.execute("SELECT changes()").fetchone()[0] > 0:
                    self.audit.append(message['id'], None, 'expired', 'system',
                                      {'reason': 'expires_at elapsed'}, db)
            Database.commit()
        except Exception:
            Database.rollback()
            raise

    def _reap_claims(self):
        """Reap bounded batches so workers get the write lock between batches."""
        while self._reap_claim_batch(limit=100):
            if self._stop.is_set():
                return

    def _reap_claim_batch(self, limit: int = 100) -> int:
        """Reap up to *limit* expired claims in one transaction."""
        try:
            db = Database.begin()
            expired = db.execute(
                """SELECT id, message_id, claimed_by, retry_count, max_retries,
                          lease_fencing_token
                   FROM message_deliveries d
                   WHERE d.state='claimed' AND d.lease_expires_at < ?
                     AND NOT EXISTS (
                       SELECT 1 FROM messages m
                       WHERE m.id = d.message_id AND m.state IN ('cancelled','expired')
                     )
                   ORDER BY d.lease_expires_at, d.id
                   LIMIT ?""",
                (now_utc(), limit),
            ).fetchall()
            for d in expired:
                rc = d['retry_count'] + 1
                if rc >= d['max_retries']:
                    # claimed → failed → dead_lettered
                    execute_with_retry(db,
                        """UPDATE message_deliveries
                           SET state='failed', last_error='lease_expired_max'
                           WHERE id=? AND state='claimed' AND lease_fencing_token=?""",
                        (d['id'], d['lease_fencing_token']),
                    )
                    if db.execute("SELECT changes()").fetchone()[0] > 0:
                        self.audit.append(d['message_id'], d['id'], 'failed',
                                          'system', {'reason': 'lease_expired'}, db)
                        db.execute(
                            "UPDATE message_deliveries SET state='dead_lettered' WHERE id=? AND state='failed'",
                            (d['id'],),
                        )
                        self.audit.append(d['message_id'], d['id'], 'dead_lettered',
                                          'system', {'reason': 'lease_expired'}, db)
                else:
                    backoff = min(300, 2 * (2 ** (rc - 1)))
                    next_at = (datetime.now(timezone.utc) + timedelta(seconds=backoff)).strftime('%Y-%m-%d %H:%M:%S')
                    execute_with_retry(db,
                        """UPDATE message_deliveries
                           SET state='retry_scheduled', retry_count=?, last_error='lease_expired',
                               next_attempt_at=?, lease_fencing_token=NULL,
                               claimed_by=NULL, claimed_at=NULL, lease_expires_at=NULL
                           WHERE id=? AND state='claimed' AND lease_fencing_token=?""",
                        (rc, next_at, d['id'], d['lease_fencing_token']),
                    )
                    if db.execute("SELECT changes()").fetchone()[0] > 0:
                        self.audit.append(d['message_id'], d['id'], 'lease_expired',
                                          'system', {'prev': d['claimed_by'], 'next': next_at}, db)
            Database.commit()
            return len(expired)
        except Exception:
            Database.rollback()
            raise

    def stop(self):
        self._stop.set()

Reaper = LeaseReaper

