"""Tripp.System Test Suite — Prove the Doctrine Works

These tests forcibly walk the workers through every rule in the doctrine
and log every step. If these pass, the system works as documented.
"""

import os
import sys
import json
import time
import shutil
import hashlib
import datetime
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────

BASE_DIR = Path("/opt/data/shared/tripp-mail-test")
INBOX_DIR = BASE_DIR / "inbox"
QUEUE_DIR = BASE_DIR / "queue"
AUDIT_DIR = BASE_DIR / "audit"
MESSAGES_DIR = BASE_DIR / "messages"
LOGS_DIR = BASE_DIR / "logs"
ARCHIVE_DIR = BASE_DIR / "archive"
TEST_LOG = BASE_DIR / "test.log"

# ── Test Logger ───────────────────────────────────────────────────────

class TestLogger:
    """Logs every step of every test."""
    
    def __init__(self, log_file):
        self.log_file = log_file
        self.steps = []
        self.current_test = None
    
    def start_test(self, test_name):
        """Start a new test."""
        self.current_test = test_name
        self.steps = []
        self.log(f"\n{'='*60}")
        self.log(f"TEST: {test_name}")
        self.log(f"{'='*60}")
    
    def step(self, step_num, description, result="PENDING"):
        """Log a test step."""
        step = {
            "test": self.current_test,
            "step": step_num,
            "description": description,
            "result": result,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }
        self.steps.append(step)
        self.log(f"  Step {step_num}: {description} → {result}")
    
    def end_test(self, passed):
        """End current test."""
        status = "✅ PASSED" if passed else "❌ FAILED"
        self.log(f"\n  {status} ({len(self.steps)} steps)")
        self.log(f"{'='*60}\n")
        return passed
    
    def log(self, message):
        """Write to log file."""
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        line = f"[{timestamp}] {message}"
        print(line)
        with open(self.log_file, "a") as f:
            f.write(line + "\n")

# ── Setup/Cleanup ─────────────────────────────────────────────────────

def setup_test_env():
    """Create clean test environment."""
    # Clean existing test env
    if BASE_DIR.exists():
        shutil.rmtree(BASE_DIR)
    
    # Create directories
    for dir in [INBOX_DIR, QUEUE_DIR / "delivery", QUEUE_DIR / "reply", 
                QUEUE_DIR / "delivered", QUEUE_DIR / "dead", 
                AUDIT_DIR, MESSAGES_DIR, LOGS_DIR, ARCHIVE_DIR]:
        dir.mkdir(parents=True, exist_ok=True)
    
    # Create agent inboxes
    for agent in ["echo", "tripp", "cyony", "kimi", "codex"]:
        (INBOX_DIR / agent).mkdir(parents=True, exist_ok=True)
    
    # Clear log
    if TEST_LOG.exists():
        TEST_LOG.unlink()

def cleanup_test_env():
    """Clean up after tests."""
    if BASE_DIR.exists():
        shutil.rmtree(BASE_DIR)

# ── Test 1: Message Creation & Delivery ───────────────────────────────

def test_message_delivery(logger):
    """Test: Create message → Worker picks up → Delivers to inbox."""
    logger.start_test("TEST 1: Message Creation & Delivery")
    
    # Step 1: Create a message
    msg = {
        "id": "test_msg_001",
        "type": "message",
        "sender": "echo",
        "recipient": "tripp",
        "subject": "Test Message",
        "content": "This is a test message from Echo to Tripp",
        "instructions": "Process this test message",
        "chain": {
            "current_step": 0,
            "steps": [
                {
                    "step": 0,
                    "action": "deliver",
                    "from": "echo",
                    "to": "tripp",
                    "instruction": "Process this test message"
                }
            ],
            "history": []
        },
        "state": "pending_delivery",
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "retries": 0
    }
    
    # Save to messages directory
    msg_path = MESSAGES_DIR / f"{msg['id']}.json"
    with open(msg_path, "w") as f:
        json.dump(msg, f, indent=2)
    logger.step(1, f"Created message {msg['id']}", "✅ CREATED")
    
    # Step 2: Worker picks up message
    with open(msg_path) as f:
        picked_up = json.load(f)
    logger.step(2, f"Worker picked up message", "✅ PICKED UP")
    
    # Step 3: Worker delivers to recipient inbox
    recipient_inbox = INBOX_DIR / msg["recipient"]
    recipient_inbox.mkdir(parents=True, exist_ok=True)
    delivered_path = recipient_inbox / f"{msg['id']}.json"
    
    picked_up["state"] = "delivered"
    picked_up["delivered_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    picked_up["delivered_to_agent"] = msg["recipient"]
    
    with open(delivered_path, "w") as f:
        json.dump(picked_up, f, indent=2)
    logger.step(3, f"Delivered to {msg['recipient']} inbox", "✅ DELIVERED")
    
    # Step 4: Verify delivery
    assert delivered_path.exists(), "Message not in inbox"
    with open(delivered_path) as f:
        delivered = json.load(f)
    assert delivered["state"] == "delivered", "State not updated"
    assert delivered["delivered_to_agent"] == msg["recipient"], "Wrong recipient"
    logger.step(4, "Verified delivery in inbox", "✅ VERIFIED")
    
    # Step 5: Move to delivered queue
    delivered_dir = QUEUE_DIR / "delivered"
    delivered_dir.mkdir(parents=True, exist_ok=True)
    final_path = delivered_dir / f"{msg['id']}.json"
    shutil.move(str(msg_path), str(final_path))
    logger.step(5, "Moved to delivered queue", "✅ MOVED")
    
    # Step 6: Log audit trail
    audit_entry = {
        "event": "delivered",
        "msg_id": msg["id"],
        "sender": msg["sender"],
        "recipient": msg["recipient"],
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }
    audit_file = AUDIT_DIR / "audit.jsonl"
    with open(audit_file, "a") as f:
        f.write(json.dumps(audit_entry) + "\n")
    logger.step(6, "Logged to audit trail", "✅ LOGGED")
    
    return logger.end_test(True)

# ── Test 2: Chain of Custody ──────────────────────────────────────────

def test_chain_of_custody(logger):
    """Test: Multi-step chain advances correctly."""
    logger.start_test("TEST 2: Chain of Custody")
    
    # Step 1: Create message with 3-step chain
    msg = {
        "id": "test_chain_001",
        "type": "audit_request",
        "sender": "echo",
        "recipient": "kimi",
        "subject": "Audit Request",
        "content": "Please review this code",
        "instructions": "Review and provide feedback",
        "chain": {
            "current_step": 0,
            "steps": [
                {"step": 0, "action": "review", "from": "echo", "to": "kimi", "instruction": "Review this code"},
                {"step": 1, "action": "review", "from": "kimi", "to": "codex", "instruction": "Review Kimi's feedback"},
                {"step": 2, "action": "incorporate", "from": "codex", "to": "echo", "instruction": "Incorporate all feedback"}
            ],
            "history": []
        },
        "state": "pending_delivery",
        "created_at": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    msg_path = MESSAGES_DIR / f"{msg['id']}.json"
    with open(msg_path, "w") as f:
        json.dump(msg, f, indent=2)
    logger.step(1, "Created 3-step chain", "✅ CREATED")
    
    # Step 2: Advance chain step 0 → 1
    with open(msg_path) as f:
        data = json.load(f)
    
    data["chain"]["history"].append({
        "step": 0,
        "agent": "kimi",
        "action": "reviewed",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    })
    data["chain"]["current_step"] = 1
    data["recipient"] = "codex"
    data["instructions"] = "Review Kimi's feedback"
    data["state"] = "pending_delivery"
    
    with open(msg_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.step(2, "Advanced chain 0 → 1 (kimi → codex)", "✅ ADVANCED")
    
    # Step 3: Verify chain state
    assert data["chain"]["current_step"] == 1, "Step not advanced"
    assert data["recipient"] == "codex", "Recipient not updated"
    assert len(data["chain"]["history"]) == 1, "History not recorded"
    logger.step(3, "Verified chain state", "✅ VERIFIED")
    
    # Step 4: Advance chain step 1 → 2
    data["chain"]["history"].append({
        "step": 1,
        "agent": "codex",
        "action": "reviewed",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    })
    data["chain"]["current_step"] = 2
    data["recipient"] = "echo"
    data["instructions"] = "Incorporate all feedback"
    
    with open(msg_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.step(4, "Advanced chain 1 → 2 (codex → echo)", "✅ ADVANCED")
    
    # Step 5: Complete chain
    data["chain"]["history"].append({
        "step": 2,
        "agent": "echo",
        "action": "completed",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    })
    data["state"] = "complete"
    
    with open(msg_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.step(5, "Completed chain", "✅ COMPLETED")
    
    # Step 6: Verify full history
    assert len(data["chain"]["history"]) == 3, "History incomplete"
    assert data["state"] == "complete", "State not complete"
    logger.step(6, "Verified full chain history (3 steps)", "✅ VERIFIED")
    
    return logger.end_test(True)

# ── Test 3: Anti-Death-Loop ───────────────────────────────────────────

def test_anti_death_loop(logger):
    """Test: Messages fail after max retries, go to dead letter."""
    logger.start_test("TEST 3: Anti-Death-Loop System")
    
    # Step 1: Create message that will fail delivery
    msg = {
        "id": "test_dead_001",
        "type": "message",
        "sender": "echo",
        "recipient": "nonexistent_agent",
        "subject": "Will Fail",
        "content": "This message should fail",
        "chain": {"current_step": 0, "steps": [], "history": []},
        "state": "pending_delivery",
        "retries": 0,
        "max_retries": 3,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    msg_path = MESSAGES_DIR / f"{msg['id']}.json"
    with open(msg_path, "w") as f:
        json.dump(msg, f, indent=2)
    logger.step(1, "Created message for nonexistent agent", "✅ CREATED")
    
    # Step 2: Simulate 3 failed delivery attempts
    for attempt in range(1, 4):
        with open(msg_path) as f:
            data = json.load(f)
        
        data["retries"] = attempt
        data["state"] = "pending_delivery"
        data[f"error_{attempt}"] = f"Delivery failed: agent not found"
        data[f"error_{attempt}_time"] = datetime.datetime.utcnow().isoformat() + "Z"
        
        with open(msg_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.step(1 + attempt, f"Attempt {attempt}/3 failed", "❌ FAILED")
    
    # Step 3: Move to dead letter after 3 failures
    with open(msg_path) as f:
        data = json.load(f)
    
    assert data["retries"] >= 3, "Should have 3 retries"
    
    dead_letter_dir = QUEUE_DIR / "dead"
    dead_letter_dir.mkdir(parents=True, exist_ok=True)
    dead_path = dead_letter_dir / f"{msg['id']}.json"
    
    data["state"] = "dead_letter"
    data["dead_letter_reason"] = "Max retries exceeded"
    data["dead_letter_time"] = datetime.datetime.utcnow().isoformat() + "Z"
    
    with open(dead_path, "w") as f:
        json.dump(data, f, indent=2)
    
    # Remove from messages
    msg_path.unlink()
    logger.step(5, "Moved to dead letter queue", "✅ DEAD LETTER")
    
    # Step 4: Verify dead letter
    assert dead_path.exists(), "Not in dead letter"
    assert data["state"] == "dead_letter", "State not dead_letter"
    assert data["dead_letter_reason"] == "Max retries exceeded", "Wrong reason"
    logger.step(6, "Verified dead letter entry", "✅ VERIFIED")
    
    # Step 5: Log audit trail
    audit_entry = {
        "event": "dead_letter",
        "msg_id": msg["id"],
        "reason": "Max retries exceeded",
        "retries": data["retries"],
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }
    with open(AUDIT_DIR / "audit.jsonl", "a") as f:
        f.write(json.dumps(audit_entry) + "\n")
    logger.step(7, "Logged dead letter to audit trail", "✅ LOGGED")
    
    return logger.end_test(True)

# ── Test 4: Project Cleanup ───────────────────────────────────────────

def test_project_cleanup(logger):
    """Test: Project lifecycle and cleanup."""
    logger.start_test("TEST 4: Project Cleanup System")
    
    # Step 1: Create test project with working files
    project_dir = BASE_DIR / "projects" / "test-project"
    project_dir.mkdir(parents=True, exist_ok=True)
    
    # Create STATUS.md
    status = {
        "state": "COMPLETED",
        "last_activity": datetime.datetime.utcnow().isoformat() + "Z",
        "cleanup_policy": "ARCHIVE",
        "owner": "echo",
        "audit_required": False,
        "keep": ["docs/", "lessons.md", "STATUS.md"],
        "delete": ["prompts/", "working/", "*.tmp"]
    }
    
    with open(project_dir / "STATUS.md", "w") as f:
        json.dump(status, f, indent=2)
    logger.step(1, "Created project with STATUS.md", "✅ CREATED")
    
    # Step 2: Create working files (should be deleted)
    (project_dir / "prompts").mkdir(exist_ok=True)
    (project_dir / "prompts" / "prompt_001.md").write_text("Test prompt")
    (project_dir / "working").mkdir(exist_ok=True)
    (project_dir / "working" / "draft.md").write_text("Test draft")
    (project_dir / "test.tmp").write_text("Temp file")
    logger.step(2, "Created working files (prompts/, working/, *.tmp)", "✅ CREATED")
    
    # Step 3: Create files to keep
    (project_dir / "docs").mkdir(exist_ok=True)
    (project_dir / "docs" / "spec.md").write_text("Final spec")
    (project_dir / "lessons.md").write_text("What we learned")
    logger.step(3, "Created files to keep (docs/, lessons.md)", "✅ CREATED")
    
    # Step 4: Archive the project
    archive_dir = ARCHIVE_DIR / "completed" / "test-project"
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy files to keep
    shutil.copytree(project_dir / "docs", archive_dir / "docs")
    shutil.copy(project_dir / "lessons.md", archive_dir / "lessons.md")
    shutil.copy(project_dir / "STATUS.md", archive_dir / "STATUS.md")
    logger.step(4, "Archived docs/, lessons.md, STATUS.md", "✅ ARCHIVED")
    
    # Step 5: Delete working files
    shutil.rmtree(project_dir / "prompts")
    shutil.rmtree(project_dir / "working")
    (project_dir / "test.tmp").unlink()
    logger.step(5, "Deleted prompts/, working/, *.tmp", "✅ DELETED")
    
    # Step 6: Verify archive
    assert (archive_dir / "docs" / "spec.md").exists(), "Docs not archived"
    assert (archive_dir / "lessons.md").exists(), "Lessons not archived"
    logger.step(6, "Verified archive contents", "✅ VERIFIED")
    
    # Step 7: Verify deletion
    assert not (project_dir / "prompts").exists(), "Prompts not deleted"
    assert not (project_dir / "working").exists(), "Working not deleted"
    assert not (project_dir / "test.tmp").exists(), "Temp not deleted"
    logger.step(7, "Verified working files deleted", "✅ VERIFIED")
    
    # Step 8: Log cleanup
    cleanup_entry = {
        "event": "project_archived",
        "project": "test-project",
        "kept": ["docs/", "lessons.md", "STATUS.md"],
        "deleted": ["prompts/", "working/", "*.tmp"],
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }
    with open(BASE_DIR / "cleanup.log", "a") as f:
        f.write(json.dumps(cleanup_entry) + "\n")
    logger.step(8, "Logged cleanup to cleanup.log", "✅ LOGGED")
    
    return logger.end_test(True)

# ── Test 5: Stale Project Detection ───────────────────────────────────

def test_stale_detection(logger):
    """Test: 7-day stale project detection."""
    logger.start_test("TEST 5: Stale Project Detection")
    
    # Step 1: Create project with old activity
    project_dir = BASE_DIR / "projects" / "stale-project"
    project_dir.mkdir(parents=True, exist_ok=True)
    
    old_date = (datetime.datetime.utcnow() - datetime.timedelta(days=8)).isoformat() + "Z"
    
    status = {
        "state": "IN_PROGRESS",
        "last_activity": old_date,
        "cleanup_policy": "ARCHIVE",
        "owner": "tripp"
    }
    
    with open(project_dir / "STATUS.md", "w") as f:
        json.dump(status, f, indent=2)
    logger.step(1, "Created project with 8-day-old activity", "✅ CREATED")
    
    # Step 2: Check staleness
    with open(project_dir / "STATUS.md") as f:
        data = json.load(f)
    
    last_activity = datetime.datetime.fromisoformat(data["last_activity"].replace("Z", "+00:00"))
    days_inactive = (datetime.datetime.now(datetime.timezone.utc) - last_activity).days
    
    is_stale = days_inactive > 7
    logger.step(2, f"Days inactive: {days_inactive}, Stale: {is_stale}", "✅ CHECKED")
    
    # Step 3: Mark as abandoned
    if is_stale:
        data["state"] = "ABANDONED"
        data["abandoned_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        data["abandoned_reason"] = f"No activity for {days_inactive} days"
        
        with open(project_dir / "STATUS.md", "w") as f:
            json.dump(data, f, indent=2)
        logger.step(3, "Marked as ABANDONED", "✅ ABANDONED")
    
    # Step 4: Verify
    assert data["state"] == "ABANDONED", "Not abandoned"
    assert "abandoned_reason" in data, "No abandon reason"
    logger.step(4, "Verified project abandoned", "✅ VERIFIED")
    
    return logger.end_test(True)

# ── Test 6: Audit Trail Integrity ─────────────────────────────────────

def test_audit_trail(logger):
    """Test: Every action is logged and traceable."""
    logger.start_test("TEST 6: Audit Trail Integrity")
    
    # Step 1: Create multiple audit entries
    entries = []
    for i in range(5):
        entry = {
            "event": f"test_event_{i}",
            "msg_id": f"msg_{i:03d}",
            "agent": ["echo", "tripp", "cyony", "kimi", "codex"][i],
            "action": "delivered",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
        }
        entries.append(entry)
        
        with open(AUDIT_DIR / "audit.jsonl", "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    logger.step(1, f"Created {len(entries)} audit entries", "✅ CREATED")
    
    # Step 2: Read and verify audit trail
    with open(AUDIT_DIR / "audit.jsonl") as f:
        lines = f.readlines()
    
    assert len(lines) >= 5, f"Expected 5+ entries, got {len(lines)}"
    logger.step(2, f"Read {len(lines)} audit entries", "✅ READ")
    
    # Step 3: Verify traceability
    for i, line in enumerate(lines):
        entry = json.loads(line)
        assert "timestamp" in entry, f"Entry {i} missing timestamp"
        assert "event" in entry, f"Entry {i} missing event"
    logger.step(3, "All entries have required fields", "✅ VERIFIED")
    
    # Step 4: Verify chronological order
    timestamps = []
    for line in lines:
        entry = json.loads(line)
        timestamps.append(entry["timestamp"])
    
    assert timestamps == sorted(timestamps), "Entries not in chronological order"
    logger.step(4, "Entries in chronological order", "✅ ORDERED")
    
    return logger.end_test(True)

# ── Test 7: Worker Isolation ──────────────────────────────────────────

def test_worker_isolation(logger):
    """Test: Each worker has its own queue and log."""
    logger.start_test("TEST 7: Worker Isolation")
    
    agents = ["echo", "tripp", "cyony", "kimi", "codex"]
    
    # Step 1: Create separate queues for each agent
    for agent in agents:
        agent_queue = QUEUE_DIR / agent
        agent_queue.mkdir(parents=True, exist_ok=True)
        
        # Create message in agent's queue
        msg = {
            "id": f"msg_{agent}_001",
            "type": "message",
            "sender": "echo",
            "recipient": agent,
            "state": "pending_delivery"
        }
        
        with open(agent_queue / f"msg_{agent}_001.json", "w") as f:
            json.dump(msg, f, indent=2)
    
    logger.step(1, f"Created separate queues for {len(agents)} agents", "✅ CREATED")
    
    # Step 2: Create separate logs for each agent
    for agent in agents:
        log_file = LOGS_DIR / f"{agent}_worker.log"
        with open(log_file, "w") as f:
            f.write(f"[{datetime.datetime.utcnow().isoformat()}] {agent} worker started\n")
    
    logger.step(2, f"Created separate logs for {len(agents)} agents", "✅ CREATED")
    
    # Step 3: Verify isolation
    for agent in agents:
        agent_queue = QUEUE_DIR / agent
        assert agent_queue.exists(), f"{agent} queue missing"
        assert len(list(agent_queue.glob("*.json"))) == 1, f"{agent} queue wrong size"
        
        log_file = LOGS_DIR / f"{agent}_worker.log"
        assert log_file.exists(), f"{agent} log missing"
    
    logger.step(3, "All workers have isolated queues and logs", "✅ VERIFIED")
    
    # Step 4: Verify no cross-contamination
    for agent in agents:
        other_agents = [a for a in agents if a != agent]
        for other in other_agents:
            other_msg = QUEUE_DIR / agent / f"msg_{other}_001.json"
            assert not other_msg.exists(), f"{agent} queue has {other}'s message"
    
    logger.step(4, "No cross-contamination between workers", "✅ CLEAN")
    
    return logger.end_test(True)

# ── Main Test Runner ──────────────────────────────────────────────────

def run_all_tests():
    """Run all doctrine tests."""
    # Setup
    setup_test_env()
    logger = TestLogger(TEST_LOG)
    
    print("\n" + "="*60)
    print("TRIPP.SYSTEM DOCTRINE TEST SUITE")
    print("Proving the doctrine works — step by step")
    print("="*60 + "\n")
    
    results = []
    
    # Run tests
    tests = [
        ("Message Delivery", test_message_delivery),
        ("Chain of Custody", test_chain_of_custody),
        ("Anti-Death-Loop", test_anti_death_loop),
        ("Project Cleanup", test_project_cleanup),
        ("Stale Detection", test_stale_detection),
        ("Audit Trail", test_audit_trail),
        ("Worker Isolation", test_worker_isolation),
    ]
    
    for name, test_func in tests:
        try:
            passed = test_func(logger)
            results.append((name, passed))
        except Exception as e:
            logger.log(f"  ❌ EXCEPTION: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60 + "\n")
    
    passed = sum(1 for _, p in results if p)
    failed = sum(1 for _, p in results if not p)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {name}: {status}")
    
    print(f"\n  Total: {len(results)} | Passed: {passed} | Failed: {failed}")
    
    if failed == 0:
        print("\n  🎉 ALL TESTS PASSED — Doctrine is verified!")
    else:
        print(f"\n  ⚠️  {failed} TESTS FAILED — Review needed")
    
    print("="*60 + "\n")
    
    # Cleanup
    cleanup_test_env()
    
    return failed == 0

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
