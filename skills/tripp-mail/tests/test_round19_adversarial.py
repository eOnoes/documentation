import unittest
import tempfile
import os
import sqlite3
import hashlib
import json
import threading

# ── Inline schema (COMPLETE DDL from v8.4 above) ──────────────
SCHEMA_SQL = r"""
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE agents (
    id TEXT PRIMARY KEY CHECK (id IN ('echo','tripp','cyony','kimi','codex','eddie','system','all')),
    name TEXT NOT NULL, api_key_hash TEXT,
    quarantine_status TEXT NOT NULL DEFAULT 'active' CHECK (quarantine_status IN ('active','quarantined','disabled')),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO agents (id,name,api_key_hash) VALUES
('echo','Echo',NULL),('tripp','Tripp',NULL),('cyony','Cyony',NULL),
('kimi','Kimi',NULL),('codex','Codex',NULL),('eddie','Eddie',NULL),
('system','System',NULL),('all','All Agents',NULL);

CREATE TABLE authorization_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT NOT NULL, recipient TEXT, message_type TEXT NOT NULL,
    allowed INTEGER NOT NULL DEFAULT 1 CHECK (allowed IN (0,1)),
    created_by TEXT NOT NULL CHECK (created_by IN ('eddie')),
    FOREIGN KEY (sender) REFERENCES agents(id),
    FOREIGN KEY (created_by) REFERENCES agents(id),
    UNIQUE(sender,recipient,message_type)
);
INSERT INTO authorization_rules (sender,recipient,message_type,allowed,created_by) VALUES
('echo','tripp','message',1,'eddie'),('echo','cyony','message',1,'eddie'),
('echo','kimi','message',1,'eddie'),('echo','codex','message',1,'eddie'),
('echo','eddie','message',1,'eddie'),('echo','all','message',1,'eddie'),
('tripp','echo','message',1,'eddie'),('tripp','cyony','message',1,'eddie'),
('tripp','kimi','message',1,'eddie'),('tripp','codex','message',1,'eddie'),
('tripp','eddie','message',1,'eddie'),('tripp','all','message',1,'eddie'),
('cyony','echo','message',1,'eddie'),('cyony','tripp','message',1,'eddie'),
('cyony','kimi','message',1,'eddie'),('cyony','codex','message',1,'eddie'),
('cyony','eddie','message',1,'eddie'),('cyony','all','message',1,'eddie'),
('kimi','echo','message',1,'eddie'),('kimi','tripp','message',1,'eddie'),
('kimi','cyony','message',1,'eddie'),('kimi','codex','message',1,'eddie'),
('kimi','eddie','message',1,'eddie'),('kimi','all','message',1,'eddie'),
('codex','echo','message',1,'eddie'),('codex','tripp','message',1,'eddie'),
('codex','cyony','message',1,'eddie'),('codex','kimi','message',1,'eddie'),
('codex','eddie','message',1,'eddie'),('codex','all','message',1,'eddie'),
('eddie','echo','message',1,'eddie'),('eddie','tripp','message',1,'eddie'),
('eddie','cyony','message',1,'eddie'),('eddie','kimi','message',1,'eddie'),
('eddie','codex','message',1,'eddie'),('eddie','all','message',1,'eddie'),
-- Also seed reply type so test_msg_types works
('echo','tripp','reply',1,'eddie'),('echo','cyony','reply',1,'eddie'),
('echo','kimi','reply',1,'eddie'),('echo','codex','reply',1,'eddie'),
('echo','eddie','reply',1,'eddie'),('echo','all','reply',1,'eddie'),
('tripp','echo','reply',1,'eddie'),('tripp','cyony','reply',1,'eddie'),
('tripp','kimi','reply',1,'eddie'),('tripp','codex','reply',1,'eddie'),
('tripp','eddie','reply',1,'eddie'),('tripp','all','reply',1,'eddie'),
('eddie','echo','reply',1,'eddie'),('eddie','tripp','reply',1,'eddie'),
('eddie','cyony','reply',1,'eddie'),('eddie','kimi','reply',1,'eddie'),
('eddie','codex','reply',1,'eddie'),('eddie','all','reply',1,'eddie'),
-- update
('echo','tripp','update',1,'eddie'),('echo','eddie','update',1,'eddie'),
('echo','all','update',1,'eddie'),('tripp','echo','update',1,'eddie'),
('tripp','eddie','update',1,'eddie'),('eddie','echo','update',1,'eddie'),
('eddie','tripp','update',1,'eddie'),('eddie','all','update',1,'eddie'),
-- request
('echo','tripp','request',1,'eddie'),('echo','eddie','request',1,'eddie'),
('eddie','echo','request',1,'eddie'),('eddie','tripp','request',1,'eddie'),
-- emergency
('echo','tripp','emergency',1,'eddie'),('echo','eddie','emergency',1,'eddie'),
('eddie','echo','emergency',1,'eddie'),('eddie','tripp','emergency',1,'eddie'),
-- audit_request
('echo','codex','audit_request',1,'eddie'),('codex','echo','audit_request',1,'eddie'),
-- audit_response
('codex','echo','audit_response',1,'eddie'),('echo','codex','audit_response',1,'eddie');

CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('message','reply','update','request','emergency','audit_request','audit_response')),
    sender TEXT NOT NULL, recipient TEXT NOT NULL, subject TEXT,
    body TEXT NOT NULL CHECK (length(body)>0 AND length(body)<=100000),
    priority INTEGER NOT NULL DEFAULT 0 CHECK (priority>=0 AND priority<=10),
    priority_aging INTEGER NOT NULL DEFAULT 0 CHECK (priority_aging>=0),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT, idempotency_key TEXT UNIQUE,
    chain_id TEXT, chain_step INTEGER DEFAULT 0 CHECK (chain_step>=0),
    chain_total INTEGER CHECK (chain_total>=1 AND chain_total<=10),
    max_steps INTEGER NOT NULL DEFAULT 10 CHECK (max_steps>=1 AND max_steps<=10),
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','claimed','delivered','failed','dead_lettered','expired','cancelled','retry_scheduled')),
    claimed_by TEXT, claimed_at TEXT, lease_expires_at TEXT, lease_fencing_token TEXT,
    delivered_at TEXT, acknowledged_at TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count>=0),
    max_retries INTEGER NOT NULL DEFAULT 3 CHECK (max_retries>=1 AND max_retries<=10),
    retry_deadline TEXT, next_attempt_at TEXT, last_error TEXT, content_hash TEXT NOT NULL,
    FOREIGN KEY (sender) REFERENCES agents(id), FOREIGN KEY (recipient) REFERENCES agents(id)
);

CREATE TABLE message_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT, message_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','claimed','delivered','failed','dead_lettered','expired','retry_scheduled')),
    claimed_by TEXT, claimed_at TEXT, lease_expires_at TEXT, lease_fencing_token TEXT,
    delivered_at TEXT, acknowledged_at TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count>=0),
    max_retries INTEGER NOT NULL DEFAULT 3 CHECK (max_retries>=1 AND max_retries<=10),
    retry_deadline TEXT, next_attempt_at TEXT, last_error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE RESTRICT,
    FOREIGN KEY (recipient_id) REFERENCES agents(id),
    FOREIGN KEY (claimed_by) REFERENCES agents(id),
    UNIQUE(message_id, recipient_id)
);

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
    message_id TEXT, delivery_id INTEGER,
    action TEXT NOT NULL CHECK (action IN ('created','claimed','delivered','acknowledged','failed','chain_advanced','dead_lettered','expired','cancelled','retry_scheduled','lease_renewed','lease_expired','auth_success','auth_failure','config_changed','health_changed','cleanup_executed','quarantine_activated','quarantine_released')),
    actor TEXT NOT NULL, details TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    previous_hash TEXT NOT NULL, record_hash TEXT NOT NULL, signature TEXT,
    FOREIGN KEY (actor) REFERENCES agents(id)
);

CREATE TABLE audit_sequence (id INTEGER PRIMARY KEY AUTOINCREMENT, last_value INTEGER NOT NULL DEFAULT 0);
INSERT INTO audit_sequence (last_value) VALUES (0);

CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);
INSERT INTO schema_version (version, description) VALUES (4, 'Tripp.System v8.4 integrated schema');

CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_log BEGIN SELECT RAISE(ABORT,'immutable'); END;
CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_log BEGIN SELECT RAISE(ABORT,'immutable'); END;

CREATE TRIGGER msg_immutable_content BEFORE UPDATE ON messages WHEN
    NEW.sender!=OLD.sender OR NEW.id!=OLD.id OR NEW.created_at!=OLD.created_at OR NEW.content_hash!=OLD.content_hash OR NEW.body!=OLD.body OR (OLD.subject IS NOT NEW.subject AND NOT (OLD.subject IS NULL AND NEW.subject IS NULL)) OR NEW.type!=OLD.type OR NEW.recipient!=OLD.recipient OR NEW.chain_id IS NOT OLD.chain_id OR NEW.chain_step!=OLD.chain_step OR NEW.chain_total!=OLD.chain_total
BEGIN SELECT RAISE(ABORT,'content immutable'); END;

CREATE TRIGGER msg_no_delete BEFORE DELETE ON messages BEGIN SELECT RAISE(ABORT,'no delete'); END;

CREATE TRIGGER authorize_insert BEFORE INSERT ON messages WHEN NEW.sender!='system' BEGIN
    SELECT RAISE(ABORT,'unauthorized') WHERE NOT EXISTS (SELECT 1 FROM authorization_rules WHERE sender=NEW.sender AND (recipient=NEW.recipient OR recipient IS NULL) AND message_type=NEW.type AND allowed=1);
END;

CREATE TRIGGER validate_active_recipient BEFORE INSERT ON messages
WHEN NEW.recipient!='all' AND NOT EXISTS (
    SELECT 1 FROM agents WHERE id=NEW.recipient AND enabled=1 AND quarantine_status='active'
) BEGIN
    SELECT RAISE(ABORT,'recipient unavailable');
END;

CREATE TRIGGER enforce_signature BEFORE INSERT ON audit_log WHEN NEW.actor!='system' AND (NEW.signature IS NULL OR length(NEW.signature)!=64 OR NEW.signature GLOB '*[^0-9a-f]*') BEGIN
    SELECT RAISE(ABORT,'signature required (64-char hex)');
END;

CREATE TRIGGER audit_hash_chain_first BEFORE INSERT ON audit_log WHEN NOT EXISTS (SELECT 1 FROM audit_log) AND NEW.previous_hash != '0000000000000000000000000000000000000000000000000000000000000000' BEGIN
    SELECT RAISE(ABORT,'first record must use zero seed');
END;

CREATE TRIGGER audit_hash_chain_verify BEFORE INSERT ON audit_log WHEN EXISTS (SELECT 1 FROM audit_log) AND NEW.previous_hash != (SELECT record_hash FROM audit_log ORDER BY id DESC LIMIT 1) BEGIN
    SELECT RAISE(ABORT,'hash chain broken');
END;

CREATE TRIGGER audit_hash_format BEFORE INSERT ON audit_log WHEN length(NEW.previous_hash)!=64 OR NEW.previous_hash GLOB '*[^0-9a-f]*' OR length(NEW.record_hash)!=64 OR NEW.record_hash GLOB '*[^0-9a-f]*' BEGIN
    SELECT RAISE(ABORT,'hash must be 64-char hex');
END;

CREATE TRIGGER broadcast_delivery AFTER INSERT ON messages WHEN NEW.recipient='all' BEGIN
    INSERT INTO message_deliveries(message_id,recipient_id,state,created_at)
    SELECT NEW.id,id,'pending',datetime('now') FROM agents WHERE id!=NEW.sender AND enabled=1 AND quarantine_status='active' AND id NOT IN ('system','all');
END;

CREATE TRIGGER single_delivery AFTER INSERT ON messages WHEN NEW.recipient!='all' BEGIN
    INSERT INTO message_deliveries(message_id,recipient_id,state,created_at)
    SELECT NEW.id,NEW.recipient,'pending',datetime('now')
    WHERE EXISTS (SELECT 1 FROM agents WHERE id=NEW.recipient AND enabled=1 AND quarantine_status='active');
END;

CREATE TRIGGER cancel_cascade AFTER UPDATE ON messages WHEN NEW.state='cancelled' AND OLD.state!='cancelled' BEGIN
    UPDATE message_deliveries SET state='expired',last_error='cancelled' WHERE message_id=NEW.id AND state IN ('pending','claimed','retry_scheduled');
END;

CREATE TRIGGER expire_cascade AFTER UPDATE ON messages WHEN NEW.state='expired' AND OLD.state!='expired' BEGIN
    UPDATE message_deliveries SET state='expired',last_error='expired' WHERE message_id=NEW.id AND state IN ('pending','claimed','retry_scheduled');
END;

CREATE TRIGGER broadcast_aggregate AFTER UPDATE ON message_deliveries WHEN OLD.state!=NEW.state AND NEW.state IN ('delivered','failed','dead_lettered','expired') BEGIN
    UPDATE messages SET state=CASE WHEN state IN ('expired','cancelled','dead_lettered') THEN state WHEN NOT EXISTS (SELECT 1 FROM message_deliveries WHERE message_id=NEW.message_id AND state NOT IN ('delivered','failed','dead_lettered','expired')) THEN CASE WHEN EXISTS (SELECT 1 FROM message_deliveries WHERE message_id=NEW.message_id AND state='delivered') THEN 'delivered' ELSE 'failed' END ELSE state END WHERE id=NEW.message_id AND recipient='all';
END;

CREATE TRIGGER single_aggregate AFTER UPDATE ON message_deliveries WHEN OLD.state!=NEW.state AND NEW.state IN ('delivered','failed','dead_lettered','expired') BEGIN
    UPDATE messages SET state=CASE WHEN state IN ('expired','cancelled','dead_lettered') THEN state ELSE NEW.state END, delivered_at=CASE WHEN NEW.state='delivered' AND state NOT IN ('expired','cancelled','dead_lettered') THEN datetime('now') ELSE delivered_at END WHERE id=NEW.message_id AND recipient!='all' AND (SELECT COUNT(*) FROM message_deliveries WHERE message_id=NEW.message_id)=1;
END;
"""

def now_utc():
    return '2026-01-01 12:00:00'

def _insert_msg(db, mid, sender='echo', recipient='tripp', typ='message', body='test body'):
    ch = hashlib.sha256(json.dumps({"id":mid,"type":typ,"sender":sender,"recipient":recipient,"subject":"","body":body,"chain_id":"","chain_step":0,"chain_total":1}, sort_keys=True, separators=(',',':')).encode()).hexdigest()
    db.execute("INSERT INTO messages(id,type,sender,recipient,body,content_hash) VALUES(?,?,?,?,?,?)",
               (mid, typ, sender, recipient, body, ch))

def _sign(actor, record_str):
    return hashlib.sha256(f"{actor}:{record_str}".encode()).hexdigest()

def _append_audit(db, mid, did, action, actor, details=None):
    seq = db.execute("UPDATE audit_sequence SET last_value=last_value+1 RETURNING last_value").fetchone()[0]
    prev = db.execute("SELECT record_hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = prev[0] if prev else "0"*64
    eid = f"{actor}:{action}:{mid}:{did}:{now_utc()}:{seq}"
    rec = {"event_id":eid,"message_id":mid,"delivery_id":did,"action":action,"actor":actor,"details":details or {}, "timestamp":now_utc(),"previous_hash":prev_hash}
    s = json.dumps(rec, sort_keys=True, separators=(',',':'))
    rh = hashlib.sha256(s.encode()).hexdigest()
    sig = _sign(actor, s) if actor != 'system' else None
    db.execute("INSERT INTO audit_log(event_id,message_id,delivery_id,action,actor,details,timestamp,previous_hash,record_hash,signature) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (eid,mid,did,action,actor,json.dumps(details or {}),now_utc(),prev_hash,rh,sig))


class TestAuthorization(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp(suffix='.db')
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA_SQL)

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_unauthorized_sender_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO messages(id,type,sender,recipient,body,content_hash) VALUES('x','message','bad','echo','hi','h')")

    def test_authorized_sender_accepted(self):
        _insert_msg(self.db, 'm1')
        self.db.commit()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 1)

    def test_unavailable_recipient_rejected(self):
        self.db.execute("UPDATE agents SET enabled=0 WHERE id='tripp'")
        with self.assertRaises(sqlite3.IntegrityError):
            _insert_msg(self.db, 'm_unavailable')
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM messages WHERE id='m_unavailable'").fetchone()[0],
            0,
        )


class TestSignatures(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp(suffix='.db')
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA_SQL)

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_unsigned_agent_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO audit_log(event_id,action,actor,details,timestamp,previous_hash,record_hash,signature) VALUES('e1','created','echo','{}','','0000000000000000000000000000000000000000000000000000000000000000','h',NULL)")

    def test_blank_signature_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO audit_log(event_id,action,actor,details,timestamp,previous_hash,record_hash,signature) VALUES('e1','created','echo','{}','','0000000000000000000000000000000000000000000000000000000000000000','h','')")

    def test_system_needs_no_signature(self):
        self.db.execute("INSERT INTO audit_log(event_id,action,actor,details,timestamp,previous_hash,record_hash,signature) VALUES('e1','created','system','{}','','0000000000000000000000000000000000000000000000000000000000000000','0000000000000000000000000000000000000000000000000000000000000000',NULL)")
        self.db.commit()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0], 1)

    def test_signed_agent_accepted(self):
        _append_audit(self.db, 'm1', 1, 'created', 'echo')
        self.db.commit()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0], 1)


class TestImmutability(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp(suffix='.db')
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA_SQL)

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_audit_no_update(self):
        _append_audit(self.db, 'm1', 1, 'created', 'system')
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE audit_log SET action='x' WHERE event_id LIKE '%'")

    def test_audit_no_delete(self):
        _append_audit(self.db, 'm1', 1, 'created', 'system')
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("DELETE FROM audit_log")

    def test_message_content_immutable(self):
        _insert_msg(self.db, 'm1')
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE messages SET body='x' WHERE id='m1'")

    def test_message_state_mutable(self):
        _insert_msg(self.db, 'm1')
        self.db.commit()
        self.db.execute("UPDATE messages SET state='claimed' WHERE id='m1'")
        self.db.commit()
        self.assertEqual(self.db.execute("SELECT state FROM messages WHERE id='m1'").fetchone()[0], 'claimed')

    def test_message_no_delete(self):
        _insert_msg(self.db, 'm1')
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("DELETE FROM messages WHERE id='m1'")


class TestBroadcast(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp(suffix='.db')
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA_SQL)

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_broadcast_creates_deliveries(self):
        _insert_msg(self.db, 'b1', sender='eddie', recipient='all')
        self.db.commit()
        count = self.db.execute("SELECT COUNT(*) FROM message_deliveries WHERE message_id='b1'").fetchone()[0]
        self.assertEqual(count, 5)  # echo, tripp, cyony, kimi, codex (not system, all, eddie)

    def test_single_creates_one_delivery(self):
        _insert_msg(self.db, 's1', sender='eddie', recipient='echo')
        self.db.commit()
        count = self.db.execute("SELECT COUNT(*) FROM message_deliveries WHERE message_id='s1'").fetchone()[0]
        self.assertEqual(count, 1)

    def test_all_delivered(self):
        _insert_msg(self.db, 'b2', sender='eddie', recipient='all')
        self.db.commit()
        self.db.execute("UPDATE message_deliveries SET state='delivered',delivered_at=datetime('now') WHERE message_id='b2'")
        self.db.commit()
        self.assertEqual(self.db.execute("SELECT state FROM messages WHERE id='b2'").fetchone()[0], 'delivered')

    def test_all_failed(self):
        _insert_msg(self.db, 'b3', sender='eddie', recipient='all')
        self.db.commit()
        self.db.execute("UPDATE message_deliveries SET state='failed' WHERE message_id='b3'")
        self.db.commit()
        self.assertEqual(self.db.execute("SELECT state FROM messages WHERE id='b3'").fetchone()[0], 'failed')

    def test_mixed_delivered_overrides_failed(self):
        _insert_msg(self.db, 'b4', sender='eddie', recipient='all')
        self.db.commit()
        dels = self.db.execute("SELECT id FROM message_deliveries WHERE message_id='b4'").fetchall()
        self.db.execute(f"UPDATE message_deliveries SET state='delivered' WHERE id={dels[0]['id']}")
        self.db.execute(f"UPDATE message_deliveries SET state='failed' WHERE id={dels[1]['id']}")
        for d in dels[2:]:
            self.db.execute(f"UPDATE message_deliveries SET state='delivered' WHERE id={d['id']}")
        self.db.commit()
        self.assertEqual(self.db.execute("SELECT state FROM messages WHERE id='b4'").fetchone()[0], 'delivered')


class TestCancellation(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp(suffix='.db')
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA_SQL)

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_cancel_cascades_to_deliveries(self):
        _insert_msg(self.db, 'c1', sender='eddie', recipient='all')
        self.db.commit()
        self.db.execute("UPDATE messages SET state='cancelled' WHERE id='c1'")
        self.db.commit()
        states = [r[0] for r in self.db.execute("SELECT state FROM message_deliveries WHERE message_id='c1'").fetchall()]
        self.assertTrue(all(s == 'expired' for s in states))

    def test_cancel_cascades_claimed_delivery(self):
        _insert_msg(self.db, 'c2', sender='eddie', recipient='echo')
        did = self.db.execute("SELECT id FROM message_deliveries WHERE message_id='c2'").fetchone()[0]
        self.db.execute(
            "UPDATE message_deliveries SET state='claimed',claimed_by='echo',lease_fencing_token='tok' WHERE id=?",
            (did,),
        )
        self.db.execute("UPDATE messages SET state='cancelled' WHERE id='c2'")
        state = self.db.execute("SELECT state FROM message_deliveries WHERE id=?", (did,)).fetchone()[0]
        self.assertEqual(state, 'expired')


class TestExpiration(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp(suffix='.db')
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA_SQL)

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_expire_cascades_to_deliveries(self):
        _insert_msg(self.db, 'e1', sender='eddie', recipient='all')
        self.db.commit()
        self.db.execute("UPDATE messages SET state='expired' WHERE id='e1'")
        self.db.commit()
        states = [r[0] for r in self.db.execute("SELECT state FROM message_deliveries WHERE message_id='e1'").fetchall()]
        self.assertTrue(all(s == 'expired' for s in states))

    def test_expire_cascades_claimed_delivery(self):
        _insert_msg(self.db, 'e_claimed', sender='eddie', recipient='echo')
        did = self.db.execute("SELECT id FROM message_deliveries WHERE message_id='e_claimed'").fetchone()[0]
        self.db.execute(
            "UPDATE message_deliveries SET state='claimed',claimed_by='echo',lease_fencing_token='tok' WHERE id=?",
            (did,),
        )
        self.db.execute("UPDATE messages SET state='expired' WHERE id='e_claimed'")
        state = self.db.execute("SELECT state FROM message_deliveries WHERE id=?", (did,)).fetchone()[0]
        self.assertEqual(state, 'expired')

    def test_due_message_expiration_sweep(self):
        _insert_msg(self.db, 'e_due', sender='eddie', recipient='echo')
        self.db.execute("UPDATE messages SET expires_at='2020-01-01 00:00:00' WHERE id='e_due'")
        self.db.execute(
            """UPDATE messages SET state='expired'
               WHERE expires_at IS NOT NULL AND expires_at <= ?
                 AND state IN ('pending','claimed','retry_scheduled')""",
            ('2026-12-31 23:59:59',),
        )
        parent = self.db.execute("SELECT state FROM messages WHERE id='e_due'").fetchone()[0]
        delivery = self.db.execute(
            "SELECT state FROM message_deliveries WHERE message_id='e_due'"
        ).fetchone()[0]
        self.assertEqual((parent, delivery), ('expired', 'expired'))

    def test_aggregate_cannot_overwrite_expired(self):
        """Even if all deliveries are 'delivered', parent must stay 'expired'."""
        _insert_msg(self.db, 'e2', sender='eddie', recipient='all')
        self.db.commit()
        self.db.execute("UPDATE messages SET state='expired' WHERE id='e2'")
        self.db.commit()
        # Now try to deliver all deliveries (shouldn't change parent)
        self.db.execute("UPDATE message_deliveries SET state='delivered' WHERE message_id='e2'")
        self.db.commit()
        self.assertEqual(self.db.execute("SELECT state FROM messages WHERE id='e2'").fetchone()[0], 'expired')


class TestConcurrency(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp(suffix='.db')
        self.db1 = sqlite3.connect(self.path, timeout=10)
        self.db1.row_factory = sqlite3.Row
        self.db1.execute("PRAGMA journal_mode=WAL")
        self.db1.execute("PRAGMA foreign_keys=ON")
        self.db1.executescript(SCHEMA_SQL)
        self.db2 = sqlite3.connect(self.path, timeout=10)
        self.db2.row_factory = sqlite3.Row
        self.db2.execute("PRAGMA journal_mode=WAL")
        self.db2.execute("PRAGMA foreign_keys=ON")

    def tearDown(self):
        self.db1.close()
        self.db2.close()
        os.unlink(self.path)

    def test_competing_claims(self):
        _insert_msg(self.db1, 'cc1', sender='eddie', recipient='echo')
        self.db1.commit()
        # Get the one delivery's ID
        did = self.db1.execute("SELECT id FROM message_deliveries WHERE message_id='cc1'").fetchone()[0]
        # Worker 1 claims it
        self.db1.execute(
            """UPDATE message_deliveries SET state='claimed',claimed_by='echo'
               WHERE id=? AND state='pending'""", (did,)
        )
        self.db1.commit()
        # Worker 2 tries to claim the SAME delivery by ID
        result = self.db2.execute(
            """UPDATE message_deliveries SET state='claimed',claimed_by='tripp'
               WHERE id=? AND state='pending'""", (did,)
        )
        self.db2.commit()
        self.assertEqual(result.rowcount, 0)


class TestHashChain(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp(suffix='.db')
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA_SQL)

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_hash_chain_detects_forgery(self):
        _append_audit(self.db, 'm1', 1, 'created', 'system')
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                """INSERT INTO audit_log(event_id,action,actor,details,timestamp,previous_hash,record_hash,signature)
                   VALUES('forged','created','system','{}','','FORGED_HASH','hash',NULL)"""
            )

    def test_hash_chain_valid(self):
        _append_audit(self.db, 'm1', 1, 'created', 'system')
        _append_audit(self.db, 'm1', 1, 'claimed', 'echo')
        self.db.commit()
        records = self.db.execute("SELECT * FROM audit_log ORDER BY id").fetchall()
        prev = "0"*64
        for r in records:
            self.assertEqual(r['previous_hash'], prev)
            prev = r['record_hash']


class TestAllMessageTypes(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp(suffix='.db')
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA_SQL)

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_all_types_accepted(self):
        for t in ('message','reply','update','request','emergency'):
            mid = f"t_{t}"
            _insert_msg(self.db, mid, typ=t)
        # audit_request and audit_response require specific sender/recipient pairs
        _insert_msg(self.db, 't_aq', sender='echo', recipient='codex', typ='audit_request')
        _insert_msg(self.db, 't_ar', sender='codex', recipient='echo', typ='audit_response')
        self.db.commit()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 7)


class TestRegressionRound19(unittest.TestCase):
    """Regression tests retained through Codex Round 19."""
    def setUp(self):
        self.path = tempfile.mktemp(suffix='.db')
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA_SQL)

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_chain_id_immutable(self):
        """Chain-of-custody fields are immutable."""
        _insert_msg(self.db, 'r1')
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE messages SET chain_id='bad' WHERE id='r1'")

    def test_chain_step_immutable(self):
        """Chain-of-custody step is immutable."""
        _insert_msg(self.db, 'r2')
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE messages SET chain_step=99 WHERE id='r2'")

    def test_deliver_expired_parent_blocked(self):
        """Deliver() blocks expired parents (not just cancelled)."""
        _insert_msg(self.db, 'r3', sender='eddie', recipient='echo')
        self.db.commit()
        did = self.db.execute("SELECT id FROM message_deliveries WHERE message_id='r3'").fetchone()[0]
        # Claim it
        self.db.execute("UPDATE message_deliveries SET state='claimed',claimed_by='echo',lease_fencing_token='tok' WHERE id=?", (did,))
        # Expire parent
        self.db.execute("UPDATE messages SET state='expired' WHERE id='r3'")
        self.db.commit()
        # Attempt deliver — should fail (expired parent)
        result = self.db.execute(
            "UPDATE message_deliveries SET state='delivered' WHERE id=? AND state='claimed'", (did,)
        )
        self.assertEqual(result.rowcount, 0, "Expired-parent cascade must revoke the active claim")
        delivery = self.db.execute("SELECT state FROM message_deliveries WHERE id=?", (did,)).fetchone()
        self.assertEqual(delivery['state'], 'expired')
        parent = self.db.execute("SELECT state FROM messages WHERE id='r3'").fetchone()
        self.assertEqual(parent['state'], 'expired')

    def test_schema_version_exists(self):
        """Schema version table identifies the integrated v8.4 schema."""
        row = self.db.execute("SELECT version FROM schema_version WHERE version=4").fetchone()
        self.assertIsNotNone(row)

    def test_reaper_skips_cancelled_parent(self):
        """LeaseReaper does NOT retry claims under a cancelled parent."""
        _insert_msg(self.db, 'r4', sender='eddie', recipient='echo')
        self.db.commit()
        did = self.db.execute("SELECT id FROM message_deliveries WHERE message_id='r4'").fetchone()[0]
        # Claim it
        self.db.execute(
            "UPDATE message_deliveries SET state='claimed',claimed_by='echo',lease_expires_at='2020-01-01 00:00:00',lease_fencing_token='tok' WHERE id=?", (did,)
        )
        # Cancel parent BEFORE lease expires
        self.db.execute("UPDATE messages SET state='cancelled' WHERE id='r4'")
        self.db.commit()
        # Reaper query: must NOT find this delivery (parent is cancelled)
        expired = self.db.execute(
            """SELECT id FROM message_deliveries d
               WHERE d.state='claimed' AND d.lease_expires_at < ?
                 AND NOT EXISTS (
                   SELECT 1 FROM messages m WHERE m.id=d.message_id AND m.state IN ('cancelled','expired')
                 )""", ('2026-12-31 23:59:59',)
        ).fetchall()
        self.assertEqual(len(expired), 0, "Reaper must not touch claims under cancelled parent")

    def test_reaper_skips_expired_parent(self):
        """LeaseReaper does NOT retry claims under an expired parent."""
        _insert_msg(self.db, 'r5', sender='eddie', recipient='tripp')
        self.db.commit()
        did = self.db.execute("SELECT id FROM message_deliveries WHERE message_id='r5'").fetchone()[0]
        self.db.execute(
            "UPDATE message_deliveries SET state='claimed',claimed_by='tripp',lease_expires_at='2020-01-01 00:00:00',lease_fencing_token='tok' WHERE id=?", (did,)
        )
        self.db.execute("UPDATE messages SET state='expired' WHERE id='r5'")
        self.db.commit()
        expired = self.db.execute(
            """SELECT id FROM message_deliveries d
               WHERE d.state='claimed' AND d.lease_expires_at < ?
                 AND NOT EXISTS (
                   SELECT 1 FROM messages m WHERE m.id=d.message_id AND m.state IN ('cancelled','expired')
                 )""", ('2026-12-31 23:59:59',)
        ).fetchall()
        self.assertEqual(len(expired), 0, "Reaper must not touch claims under expired parent")

    def test_reaper_finds_active_parent(self):
        """LeaseReaper DOES find claims under an active parent."""
        _insert_msg(self.db, 'r6', sender='eddie', recipient='echo')
        self.db.commit()
        did = self.db.execute("SELECT id FROM message_deliveries WHERE message_id='r6'").fetchone()[0]
        self.db.execute(
            "UPDATE message_deliveries SET state='claimed',claimed_by='echo',lease_expires_at='2020-01-01 00:00:00',lease_fencing_token='tok' WHERE id=?", (did,)
        )
        # Parent stays pending (active)
        self.db.commit()
        expired = self.db.execute(
            """SELECT id FROM message_deliveries d
               WHERE d.state='claimed' AND d.lease_expires_at < ?
                 AND NOT EXISTS (
                   SELECT 1 FROM messages m WHERE m.id=d.message_id AND m.state IN ('cancelled','expired')
                 )""", ('2026-12-31 23:59:59',)
        ).fetchall()
        self.assertEqual(len(expired), 1, "Reaper MUST find claims under active parent")

    def test_reaper_respects_fencing_token(self):
        """A stale reaper observation cannot mutate a newer lease."""
        _insert_msg(self.db, 'r7', sender='eddie', recipient='echo')
        did = self.db.execute("SELECT id FROM message_deliveries WHERE message_id='r7'").fetchone()[0]
        self.db.execute(
            """UPDATE message_deliveries
               SET state='claimed',claimed_by='echo',lease_expires_at='2020-01-01 00:00:00',
                   lease_fencing_token='current-token'
               WHERE id=?""",
            (did,),
        )
        result = self.db.execute(
            """UPDATE message_deliveries SET state='retry_scheduled'
               WHERE id=? AND state='claimed' AND lease_fencing_token=?""",
            (did, 'stale-token'),
        )
        self.assertEqual(result.rowcount, 0)
        state = self.db.execute("SELECT state FROM message_deliveries WHERE id=?", (did,)).fetchone()[0]
        self.assertEqual(state, 'claimed')


if __name__ == '__main__':
    unittest.main()

