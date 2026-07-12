-- ============================================================
-- Tripp.System v8.4 — Production Schema
-- ============================================================
-- PRAGMA settings
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
PRAGMA synchronous=NORMAL;
PRAGMA wal_autocheckpoint=1000;

-- ============================================================
-- TABLES
-- ============================================================

-- Agents (includes 'system' for non-agent events, 'all' for broadcasts)
CREATE TABLE agents (
    id TEXT PRIMARY KEY CHECK (id IN ('echo', 'tripp', 'cyony', 'kimi', 'codex', 'eddie', 'system', 'all')),
    name TEXT NOT NULL,
    api_key_hash TEXT,
    quarantine_status TEXT NOT NULL DEFAULT 'active' CHECK (quarantine_status IN ('active', 'quarantined', 'disabled')),
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO agents (id, name, api_key_hash) VALUES
('echo', 'Echo', NULL), ('tripp', 'Tripp', NULL), ('cyony', 'Cyony', NULL),
('kimi', 'Kimi', NULL), ('codex', 'Codex', NULL), ('eddie', 'Eddie', NULL),
('system', 'System', NULL), ('all', 'All Agents', NULL);

-- Authorization rules (enforced at INSERT via trigger)
CREATE TABLE authorization_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT NOT NULL,
    recipient TEXT,
    message_type TEXT NOT NULL,
    allowed INTEGER NOT NULL DEFAULT 1 CHECK (allowed IN (0, 1)),
    created_by TEXT NOT NULL CHECK (created_by IN ('eddie')),
    FOREIGN KEY (sender) REFERENCES agents(id),
    FOREIGN KEY (created_by) REFERENCES agents(id),
    UNIQUE(sender, recipient, message_type)
);

-- Seed ALL authorization rules for ALL message types
INSERT INTO authorization_rules (sender, recipient, message_type, allowed, created_by) VALUES
-- message type for all agent pairs
('echo', 'tripp', 'message', 1, 'eddie'), ('echo', 'cyony', 'message', 1, 'eddie'),
('echo', 'kimi', 'message', 1, 'eddie'), ('echo', 'codex', 'message', 1, 'eddie'),
('echo', 'eddie', 'message', 1, 'eddie'),
('tripp', 'echo', 'message', 1, 'eddie'), ('tripp', 'cyony', 'message', 1, 'eddie'),
('tripp', 'kimi', 'message', 1, 'eddie'), ('tripp', 'codex', 'message', 1, 'eddie'),
('tripp', 'eddie', 'message', 1, 'eddie'),
('cyony', 'echo', 'message', 1, 'eddie'), ('cyony', 'tripp', 'message', 1, 'eddie'),
('cyony', 'kimi', 'message', 1, 'eddie'), ('cyony', 'codex', 'message', 1, 'eddie'),
('cyony', 'eddie', 'message', 1, 'eddie'),
('kimi', 'echo', 'message', 1, 'eddie'), ('kimi', 'tripp', 'message', 1, 'eddie'),
('kimi', 'cyony', 'message', 1, 'eddie'), ('kimi', 'codex', 'message', 1, 'eddie'),
('kimi', 'eddie', 'message', 1, 'eddie'),
('codex', 'echo', 'message', 1, 'eddie'), ('codex', 'tripp', 'message', 1, 'eddie'),
('codex', 'cyony', 'message', 1, 'eddie'), ('codex', 'kimi', 'message', 1, 'eddie'),
('codex', 'eddie', 'message', 1, 'eddie'),
('eddie', 'echo', 'message', 1, 'eddie'), ('eddie', 'tripp', 'message', 1, 'eddie'),
('eddie', 'cyony', 'message', 1, 'eddie'), ('eddie', 'kimi', 'message', 1, 'eddie'),
('eddie', 'codex', 'message', 1, 'eddie'),
-- broadcast
('echo', 'all', 'message', 1, 'eddie'), ('tripp', 'all', 'message', 1, 'eddie'),
('cyony', 'all', 'message', 1, 'eddie'), ('kimi', 'all', 'message', 1, 'eddie'),
('codex', 'all', 'message', 1, 'eddie'), ('eddie', 'all', 'message', 1, 'eddie'),
-- reply type
('echo', 'tripp', 'reply', 1, 'eddie'), ('echo', 'cyony', 'reply', 1, 'eddie'),
('echo', 'kimi', 'reply', 1, 'eddie'), ('echo', 'codex', 'reply', 1, 'eddie'),
('echo', 'eddie', 'reply', 1, 'eddie'),
('tripp', 'echo', 'reply', 1, 'eddie'), ('tripp', 'cyony', 'reply', 1, 'eddie'),
('tripp', 'kimi', 'reply', 1, 'eddie'), ('tripp', 'codex', 'reply', 1, 'eddie'),
('tripp', 'eddie', 'reply', 1, 'eddie'),
('cyony', 'echo', 'reply', 1, 'eddie'), ('cyony', 'tripp', 'reply', 1, 'eddie'),
('cyony', 'kimi', 'reply', 1, 'eddie'), ('cyony', 'codex', 'reply', 1, 'eddie'),
('cyony', 'eddie', 'reply', 1, 'eddie'),
('kimi', 'echo', 'reply', 1, 'eddie'), ('kimi', 'tripp', 'reply', 1, 'eddie'),
('kimi', 'cyony', 'reply', 1, 'eddie'), ('kimi', 'codex', 'reply', 1, 'eddie'),
('kimi', 'eddie', 'reply', 1, 'eddie'),
('codex', 'echo', 'reply', 1, 'eddie'), ('codex', 'tripp', 'reply', 1, 'eddie'),
('codex', 'cyony', 'reply', 1, 'eddie'), ('codex', 'kimi', 'reply', 1, 'eddie'),
('codex', 'eddie', 'reply', 1, 'eddie'),
('eddie', 'echo', 'reply', 1, 'eddie'), ('eddie', 'tripp', 'reply', 1, 'eddie'),
('eddie', 'cyony', 'reply', 1, 'eddie'), ('eddie', 'kimi', 'reply', 1, 'eddie'),
('eddie', 'codex', 'reply', 1, 'eddie'),
('echo', 'all', 'reply', 1, 'eddie'), ('tripp', 'all', 'reply', 1, 'eddie'),
('cyony', 'all', 'reply', 1, 'eddie'), ('kimi', 'all', 'reply', 1, 'eddie'),
('codex', 'all', 'reply', 1, 'eddie'), ('eddie', 'all', 'reply', 1, 'eddie'),
-- update type
('echo', 'tripp', 'update', 1, 'eddie'), ('echo', 'cyony', 'update', 1, 'eddie'),
('echo', 'kimi', 'update', 1, 'eddie'), ('echo', 'codex', 'update', 1, 'eddie'),
('echo', 'eddie', 'update', 1, 'eddie'),
('tripp', 'echo', 'update', 1, 'eddie'), ('tripp', 'cyony', 'update', 1, 'eddie'),
('tripp', 'kimi', 'update', 1, 'eddie'), ('tripp', 'codex', 'update', 1, 'eddie'),
('tripp', 'eddie', 'update', 1, 'eddie'),
('cyony', 'echo', 'update', 1, 'eddie'), ('cyony', 'tripp', 'update', 1, 'eddie'),
('cyony', 'kimi', 'update', 1, 'eddie'), ('cyony', 'codex', 'update', 1, 'eddie'),
('cyony', 'eddie', 'update', 1, 'eddie'),
('kimi', 'echo', 'update', 1, 'eddie'), ('kimi', 'tripp', 'update', 1, 'eddie'),
('kimi', 'cyony', 'update', 1, 'eddie'), ('kimi', 'codex', 'update', 1, 'eddie'),
('kimi', 'eddie', 'update', 1, 'eddie'),
('codex', 'echo', 'update', 1, 'eddie'), ('codex', 'tripp', 'update', 1, 'eddie'),
('codex', 'cyony', 'update', 1, 'eddie'), ('codex', 'kimi', 'update', 1, 'eddie'),
('codex', 'eddie', 'update', 1, 'eddie'),
('eddie', 'echo', 'update', 1, 'eddie'), ('eddie', 'tripp', 'update', 1, 'eddie'),
('eddie', 'cyony', 'update', 1, 'eddie'), ('eddie', 'kimi', 'update', 1, 'eddie'),
('eddie', 'codex', 'update', 1, 'eddie'),
('echo', 'all', 'update', 1, 'eddie'), ('tripp', 'all', 'update', 1, 'eddie'),
('cyony', 'all', 'update', 1, 'eddie'), ('kimi', 'all', 'update', 1, 'eddie'),
('codex', 'all', 'update', 1, 'eddie'), ('eddie', 'all', 'update', 1, 'eddie'),
-- request type
('echo', 'tripp', 'request', 1, 'eddie'), ('echo', 'cyony', 'request', 1, 'eddie'),
('echo', 'kimi', 'request', 1, 'eddie'), ('echo', 'codex', 'request', 1, 'eddie'),
('echo', 'eddie', 'request', 1, 'eddie'),
('tripp', 'echo', 'request', 1, 'eddie'), ('tripp', 'cyony', 'request', 1, 'eddie'),
('tripp', 'kimi', 'request', 1, 'eddie'), ('tripp', 'codex', 'request', 1, 'eddie'),
('tripp', 'eddie', 'request', 1, 'eddie'),
('cyony', 'echo', 'request', 1, 'eddie'), ('cyony', 'tripp', 'request', 1, 'eddie'),
('cyony', 'kimi', 'request', 1, 'eddie'), ('cyony', 'codex', 'request', 1, 'eddie'),
('cyony', 'eddie', 'request', 1, 'eddie'),
('kimi', 'echo', 'request', 1, 'eddie'), ('kimi', 'tripp', 'request', 1, 'eddie'),
('kimi', 'cyony', 'request', 1, 'eddie'), ('kimi', 'codex', 'request', 1, 'eddie'),
('kimi', 'eddie', 'request', 1, 'eddie'),
('codex', 'echo', 'request', 1, 'eddie'), ('codex', 'tripp', 'request', 1, 'eddie'),
('codex', 'cyony', 'request', 1, 'eddie'), ('codex', 'kimi', 'request', 1, 'eddie'),
('codex', 'eddie', 'request', 1, 'eddie'),
('eddie', 'echo', 'request', 1, 'eddie'), ('eddie', 'tripp', 'request', 1, 'eddie'),
('eddie', 'cyony', 'request', 1, 'eddie'), ('eddie', 'kimi', 'request', 1, 'eddie'),
('eddie', 'codex', 'request', 1, 'eddie'),
('echo', 'all', 'request', 1, 'eddie'), ('tripp', 'all', 'request', 1, 'eddie'),
('cyony', 'all', 'request', 1, 'eddie'), ('kimi', 'all', 'request', 1, 'eddie'),
('codex', 'all', 'request', 1, 'eddie'), ('eddie', 'all', 'request', 1, 'eddie'),
-- emergency type
('echo', 'tripp', 'emergency', 1, 'eddie'), ('echo', 'cyony', 'emergency', 1, 'eddie'),
('echo', 'kimi', 'emergency', 1, 'eddie'), ('echo', 'codex', 'emergency', 1, 'eddie'),
('echo', 'eddie', 'emergency', 1, 'eddie'),
('tripp', 'echo', 'emergency', 1, 'eddie'), ('tripp', 'cyony', 'emergency', 1, 'eddie'),
('tripp', 'kimi', 'emergency', 1, 'eddie'), ('tripp', 'codex', 'emergency', 1, 'eddie'),
('tripp', 'eddie', 'emergency', 1, 'eddie'),
('cyony', 'echo', 'emergency', 1, 'eddie'), ('cyony', 'tripp', 'emergency', 1, 'eddie'),
('cyony', 'kimi', 'emergency', 1, 'eddie'), ('cyony', 'codex', 'emergency', 1, 'eddie'),
('cyony', 'eddie', 'emergency', 1, 'eddie'),
('kimi', 'echo', 'emergency', 1, 'eddie'), ('kimi', 'tripp', 'emergency', 1, 'eddie'),
('kimi', 'cyony', 'emergency', 1, 'eddie'), ('kimi', 'codex', 'emergency', 1, 'eddie'),
('kimi', 'eddie', 'emergency', 1, 'eddie'),
('codex', 'echo', 'emergency', 1, 'eddie'), ('codex', 'tripp', 'emergency', 1, 'eddie'),
('codex', 'cyony', 'emergency', 1, 'eddie'), ('codex', 'kimi', 'emergency', 1, 'eddie'),
('codex', 'eddie', 'emergency', 1, 'eddie'),
('eddie', 'echo', 'emergency', 1, 'eddie'), ('eddie', 'tripp', 'emergency', 1, 'eddie'),
('eddie', 'cyony', 'emergency', 1, 'eddie'), ('eddie', 'kimi', 'emergency', 1, 'eddie'),
('eddie', 'codex', 'emergency', 1, 'eddie'),
('echo', 'all', 'emergency', 1, 'eddie'), ('tripp', 'all', 'emergency', 1, 'eddie'),
('cyony', 'all', 'emergency', 1, 'eddie'), ('kimi', 'all', 'emergency', 1, 'eddie'),
('codex', 'all', 'emergency', 1, 'eddie'), ('eddie', 'all', 'emergency', 1, 'eddie'),
-- audit_request type
('echo', 'codex', 'audit_request', 1, 'eddie'),
('tripp', 'codex', 'audit_request', 1, 'eddie'),
('cyony', 'codex', 'audit_request', 1, 'eddie'),
('kimi', 'codex', 'audit_request', 1, 'eddie'),
('codex', 'echo', 'audit_request', 1, 'eddie'),
('codex', 'tripp', 'audit_request', 1, 'eddie'),
('codex', 'cyony', 'audit_request', 1, 'eddie'),
('codex', 'kimi', 'audit_request', 1, 'eddie'),
('eddie', 'codex', 'audit_request', 1, 'eddie'),
-- audit_response type
('codex', 'echo', 'audit_response', 1, 'eddie'),
('codex', 'tripp', 'audit_response', 1, 'eddie'),
('codex', 'cyony', 'audit_response', 1, 'eddie'),
('codex', 'kimi', 'audit_response', 1, 'eddie'),
('echo', 'codex', 'audit_response', 1, 'eddie'),
('tripp', 'codex', 'audit_response', 1, 'eddie'),
('cyony', 'codex', 'audit_response', 1, 'eddie'),
('kimi', 'codex', 'audit_response', 1, 'eddie'),
('codex', 'eddie', 'audit_response', 1, 'eddie');

-- Messages (content fields immutable, state fields mutable)
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('message', 'reply', 'update', 'request', 'emergency', 'audit_request', 'audit_response')),
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT,
    body TEXT NOT NULL CHECK (length(body) > 0 AND length(body) <= 100000),
    priority INTEGER NOT NULL DEFAULT 0 CHECK (priority >= 0 AND priority <= 10),
    priority_aging INTEGER NOT NULL DEFAULT 0 CHECK (priority_aging >= 0),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT,
    idempotency_key TEXT UNIQUE,
    chain_id TEXT,
    chain_step INTEGER DEFAULT 0 CHECK (chain_step >= 0),
    chain_total INTEGER CHECK (chain_total >= 1 AND chain_total <= 10),
    max_steps INTEGER NOT NULL DEFAULT 10 CHECK (max_steps >= 1 AND max_steps <= 10),
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'claimed', 'delivered', 'failed', 'dead_lettered', 'expired', 'cancelled', 'retry_scheduled')),
    claimed_by TEXT,
    claimed_at TEXT,
    lease_expires_at TEXT,
    lease_fencing_token TEXT,
    delivered_at TEXT,
    acknowledged_at TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    max_retries INTEGER NOT NULL DEFAULT 3 CHECK (max_retries >= 1 AND max_retries <= 10),
    retry_deadline TEXT,
    next_attempt_at TEXT,
    last_error TEXT,
    content_hash TEXT NOT NULL,
    FOREIGN KEY (sender) REFERENCES agents(id),
    FOREIGN KEY (recipient) REFERENCES agents(id)
);

-- Message deliveries (per-recipient for broadcasts)
CREATE TABLE message_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'claimed', 'delivered', 'failed', 'dead_lettered', 'expired', 'retry_scheduled')),
    claimed_by TEXT,
    claimed_at TEXT,
    lease_expires_at TEXT,
    lease_fencing_token TEXT,
    delivered_at TEXT,
    acknowledged_at TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    max_retries INTEGER NOT NULL DEFAULT 3 CHECK (max_retries >= 1 AND max_retries <= 10),
    retry_deadline TEXT,
    next_attempt_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE RESTRICT,
    FOREIGN KEY (recipient_id) REFERENCES agents(id),
    FOREIGN KEY (claimed_by) REFERENCES agents(id),
    UNIQUE(message_id, recipient_id)
);

-- Audit trail (append-only, immutable)
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    message_id TEXT,
    delivery_id INTEGER,
    action TEXT NOT NULL CHECK (action IN ('created', 'claimed', 'delivered', 'acknowledged', 'failed', 'chain_advanced', 'dead_lettered', 'expired', 'cancelled', 'retry_scheduled', 'lease_renewed', 'lease_expired', 'auth_success', 'auth_failure', 'config_changed', 'health_changed', 'cleanup_executed', 'quarantine_activated', 'quarantine_released')),
    actor TEXT NOT NULL,
    details TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    previous_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL,
    signature TEXT,
    FOREIGN KEY (actor) REFERENCES agents(id)
);

CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);
INSERT INTO schema_version (version, description) VALUES (4, 'Tripp.System v8.4 integrated schema');

-- Worker health
CREATE TABLE worker_health (
    worker_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    last_heartbeat TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL DEFAULT 'healthy' CHECK (status IN ('healthy', 'degraded', 'dead')),
    messages_processed INTEGER NOT NULL DEFAULT 0,
    errors_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Audit sequence for deterministic event IDs
CREATE TABLE audit_sequence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    last_value INTEGER NOT NULL DEFAULT 0
);
INSERT INTO audit_sequence (last_value) VALUES (0);

-- Indexes
CREATE INDEX idx_messages_state ON messages(state);
CREATE INDEX idx_messages_recipient ON messages(recipient);
CREATE INDEX idx_messages_chain ON messages(chain_id, chain_step);
CREATE INDEX idx_messages_next_attempt ON messages(next_attempt_at) WHERE state IN ('pending', 'retry_scheduled');
CREATE INDEX idx_messages_expires ON messages(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_messages_priority ON messages(priority DESC, priority_aging DESC, created_at ASC) WHERE state = 'pending';
CREATE INDEX idx_deliveries_message ON message_deliveries(message_id);
CREATE INDEX idx_deliveries_recipient ON message_deliveries(recipient_id);
CREATE INDEX idx_deliveries_state ON message_deliveries(state);
CREATE INDEX idx_deliveries_next_attempt ON message_deliveries(next_attempt_at) WHERE state IN ('pending', 'retry_scheduled');
CREATE INDEX idx_audit_message ON audit_log(message_id);
CREATE INDEX idx_audit_delivery ON audit_log(delivery_id);
CREATE INDEX idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX idx_audit_event ON audit_log(event_id);

-- ============================================================
-- TRIGGERS (Database-enforced constraints)
-- ============================================================

-- 1. Audit immutability
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'Audit log is immutable'); END;

CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'Audit log is immutable'); END;

-- 2. Message content immutability (protects content fields only)
CREATE TRIGGER msg_immutable_content
BEFORE UPDATE ON messages
WHEN
    NEW.sender != OLD.sender
    OR NEW.id != OLD.id
    OR NEW.created_at != OLD.created_at
    OR NEW.content_hash != OLD.content_hash
    OR NEW.body != OLD.body
    OR (OLD.subject IS NOT NEW.subject AND NOT (OLD.subject IS NULL AND NEW.subject IS NULL))
    OR NEW.type != OLD.type
    OR NEW.recipient != OLD.recipient
    OR NEW.chain_id IS NOT OLD.chain_id
    OR NEW.chain_step IS NOT OLD.chain_step
    OR NEW.chain_total IS NOT OLD.chain_total
BEGIN
    SELECT RAISE(ABORT, 'Message content fields are immutable');
END;

-- 3. No-delete on messages
CREATE TRIGGER msg_no_delete BEFORE DELETE ON messages
BEGIN SELECT RAISE(ABORT, 'Messages cannot be deleted'); END;

-- 4. Authorization enforcement at INSERT
CREATE TRIGGER authorize_insert
BEFORE INSERT ON messages
WHEN NEW.sender != 'system'
BEGIN
    SELECT RAISE(ABORT, 'Unauthorized: ' || NEW.sender || ' -> ' || NEW.recipient || ' / ' || NEW.type)
    WHERE NOT EXISTS (
        SELECT 1 FROM authorization_rules
        WHERE sender = NEW.sender
        AND (recipient = NEW.recipient OR recipient IS NULL)
        AND message_type = NEW.type
        AND allowed = 1
    );
END;

-- 4b. Reject single-recipient messages that cannot create a delivery
CREATE TRIGGER validate_active_recipient
BEFORE INSERT ON messages
WHEN NEW.recipient != 'all' AND NOT EXISTS (
    SELECT 1 FROM agents
    WHERE id = NEW.recipient
      AND enabled = 1
      AND quarantine_status = 'active'
)
BEGIN
    SELECT RAISE(ABORT, 'Recipient is disabled or quarantined');
END;

-- 5. Signature enforcement at INSERT for agent audit events
CREATE TRIGGER enforce_signature
BEFORE INSERT ON audit_log
WHEN NEW.actor != 'system' AND (
    NEW.signature IS NULL
    OR length(NEW.signature) != 64
    OR NEW.signature GLOB '*[^0-9a-f]*'
)
BEGIN
    SELECT RAISE(ABORT, 'Agent audit events must have a valid 64-char lowercase hex signature');
END;

-- 5b. Hash chain enforcement (reject forged previous_hash)
CREATE TRIGGER audit_hash_chain_first
BEFORE INSERT ON audit_log
WHEN NOT EXISTS (SELECT 1 FROM audit_log)
  AND NEW.previous_hash != '0000000000000000000000000000000000000000000000000000000000000000'
BEGIN
    SELECT RAISE(ABORT, 'First audit record must use zero seed for previous_hash');
END;

CREATE TRIGGER audit_hash_chain_verify
BEFORE INSERT ON audit_log
WHEN EXISTS (SELECT 1 FROM audit_log)
  AND NEW.previous_hash != (
    SELECT record_hash FROM audit_log ORDER BY id DESC LIMIT 1
  )
BEGIN
    SELECT RAISE(ABORT, 'previous_hash must match the latest record_hash');
END;

-- Hash format constraints
CREATE TRIGGER audit_hash_format
BEFORE INSERT ON audit_log
WHEN length(NEW.previous_hash) != 64 OR NEW.previous_hash GLOB '*[^0-9a-f]*'
   OR length(NEW.record_hash) != 64 OR NEW.record_hash GLOB '*[^0-9a-f]*'
BEGIN
    SELECT RAISE(ABORT, 'previous_hash and record_hash must be 64-char lowercase hex');
END;

-- 6. Broadcast delivery trigger (create per-recipient records)
-- NOTE: 'all' is a valid FK entry in agents table, so INSERT into messages is valid.
-- The broadcast_delivery trigger expands 'all' into individual delivery rows.
CREATE TRIGGER broadcast_delivery
AFTER INSERT ON messages
WHEN NEW.recipient = 'all'
BEGIN
    INSERT INTO message_deliveries (message_id, recipient_id, state, created_at)
    SELECT NEW.id, id, 'pending', datetime('now')
    FROM agents
    WHERE id != NEW.sender
      AND enabled = 1
      AND quarantine_status = 'active'
      AND id NOT IN ('system', 'all');
END;

-- 7. Single-recipient delivery trigger
CREATE TRIGGER single_delivery
AFTER INSERT ON messages
WHEN NEW.recipient != 'all'
BEGIN
    INSERT INTO message_deliveries (message_id, recipient_id, state, created_at)
    SELECT NEW.id, NEW.recipient, 'pending', datetime('now')
    WHERE EXISTS (
        SELECT 1 FROM agents
        WHERE id = NEW.recipient
          AND enabled = 1
          AND quarantine_status = 'active'
    );
END;

-- 8. Cancellation cascade (cancel → all non-terminal deliveries become expired)
-- Fires BEFORE broadcast_aggregate so terminal state is locked first.
CREATE TRIGGER cancel_cascade
AFTER UPDATE ON messages
WHEN NEW.state = 'cancelled' AND OLD.state != 'cancelled'
BEGIN
    UPDATE message_deliveries
    SET state = 'expired', last_error = 'Parent message cancelled'
    WHERE message_id = NEW.id
      AND state IN ('pending', 'claimed', 'retry_scheduled');
END;

-- 9. Expiration cascade (expire → all non-terminal deliveries become expired)
-- Fires BEFORE broadcast_aggregate so terminal state is locked first.
CREATE TRIGGER expire_cascade
AFTER UPDATE ON messages
WHEN NEW.state = 'expired' AND OLD.state != 'expired'
BEGIN
    UPDATE message_deliveries
    SET state = 'expired', last_error = 'Parent message expired'
    WHERE message_id = NEW.id
      AND state IN ('pending', 'claimed', 'retry_scheduled');
END;

-- 10. Broadcast aggregation — derives parent state from deliveries
-- CRITICAL: If parent is already in a terminal state (expired, cancelled, dead_lettered),
-- aggregation MUST NOT overwrite it. This prevents delivery-state-changes from undoing
-- explicit worker-set terminal states.
CREATE TRIGGER broadcast_aggregate
AFTER UPDATE ON message_deliveries
WHEN OLD.state != NEW.state AND NEW.state IN ('delivered', 'failed', 'dead_lettered', 'expired')
BEGIN
    UPDATE messages
    SET state = CASE
        -- Terminal parent: never overwrite
        WHEN state IN ('expired', 'cancelled', 'dead_lettered') THEN state
        -- All deliveries terminal? delivered if ANY succeeded, else failed
        WHEN NOT EXISTS (
            SELECT 1 FROM message_deliveries
            WHERE message_id = NEW.message_id
              AND state NOT IN ('delivered', 'failed', 'dead_lettered', 'expired')
        ) THEN
            CASE WHEN EXISTS (
                SELECT 1 FROM message_deliveries
                WHERE message_id = NEW.message_id AND state = 'delivered'
            ) THEN 'delivered' ELSE 'failed' END
        -- Still pending work: keep 'pending' or 'claimed'
        ELSE state
    END,
    delivered_at = CASE
        WHEN state NOT IN ('expired', 'cancelled', 'dead_lettered')
         AND NOT EXISTS (
            SELECT 1 FROM message_deliveries
            WHERE message_id = NEW.message_id
              AND state NOT IN ('delivered', 'failed', 'dead_lettered', 'expired')
        ) THEN datetime('now')
        ELSE delivered_at
    END
    WHERE id = NEW.message_id AND recipient = 'all';
END;

-- 11. Single-recipient aggregation (sync parent state with its one delivery)
CREATE TRIGGER single_aggregate
AFTER UPDATE ON message_deliveries
WHEN OLD.state != NEW.state
  AND NEW.state IN ('delivered', 'failed', 'dead_lettered', 'expired')
BEGIN
    UPDATE messages
    SET state = CASE
        WHEN state IN ('expired', 'cancelled', 'dead_lettered') THEN state
        ELSE NEW.state
    END,
    delivered_at = CASE
        WHEN NEW.state = 'delivered' AND state NOT IN ('expired', 'cancelled', 'dead_lettered')
        THEN datetime('now') ELSE delivered_at
    END
    WHERE id = NEW.message_id
      AND recipient != 'all'
      AND (SELECT COUNT(*) FROM message_deliveries WHERE message_id = NEW.message_id) = 1;
END;

-- 12. Lease reaper: expired claims → retry_scheduled (handled by application-level reaper,
--     NOT a trigger, because reaper needs complex logic: backoff, deadline check, dead-letter)

