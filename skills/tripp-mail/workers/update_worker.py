"""Tripp.Mail — Update Courier Worker

Picks up UPDATES only.
Does NOT pick up messages, requests, or replies.
"""

import os
import json
import time
import shutil
import datetime
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────

BASE_DIR = Path("/opt/data/shared/tripp-mail")
INBOX_DIR = BASE_DIR / "inbox"
QUEUE_DIR = BASE_DIR / "queue"
AUDIT_DIR = BASE_DIR / "audit"
DEAD_LETTER_DIR = QUEUE_DIR / "dead"

MAX_RETRIES = 3
DELIVERY_TIMEOUT = 300  # 5 minutes
CHECK_INTERVAL = 30  # seconds

# ── Message Types This Worker Handles ─────────────────────────────────

# THIS WORKER ONLY HANDLES:
#   - "update"  (status update, notification, announcement)
#
# THIS WORKER DOES NOT HANDLE:
#   - "message"  (handled by delivery_worker.py)
#   - "request"  (handled by delivery_worker.py)
#   - "reply"    (handled by reply_worker.py)
#
# Updates are broadcast to ALL agents or a specific list.
# They are informational only - no response expected.

# ── Helpers ───────────────────────────────────────────────────────────

def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"

def log_audit(event):
    """Append event to audit trail."""
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_file = AUDIT_DIR / "audit.jsonl"
    with open(audit_file, "a") as f:
        f.write(json.dumps(event) + "\n")

def get_pending_updates():
    """Get updates waiting for delivery.
    
    ONLY picks up messages with type="update".
    Ignores messages, requests, and replies.
    """
    update_dir = QUEUE_DIR / "update"
    if not update_dir.exists():
        return []
    
    updates = []
    for msg_file in sorted(update_dir.glob("*.json")):
        try:
            with open(msg_file) as f:
                msg = json.load(f)
            
            # ONLY handle updates
            msg_type = msg.get("type", "")
            if msg_type != "update":
                # Not our job - skip this message
                continue
            
            msg["_file"] = str(msg_file)
            updates.append(msg)
        except Exception as e:
            print(f"Error reading {msg_file}: {e}")
    
    return updates

def deliver_update(msg):
    """Deliver update to recipient(s).
    
    If recipient is "all", deliver to all agents.
    If recipient is a list, deliver to each.
    If recipient is a single agent, deliver to that agent.
    """
    recipient = msg["recipient"]
    
    # Determine list of recipients
    if recipient == "all":
        recipients = ["echo", "tripp", "cyony", "kimi", "codex"]
    elif isinstance(recipient, list):
        recipients = recipient
    else:
        recipients = [recipient]
    
    delivered_to = []
    
    for r in recipients:
        recipient_inbox = INBOX_DIR / r
        recipient_inbox.mkdir(parents=True, exist_ok=True)
        
        # Create update file
        msg_filename = f"{msg['id']}.json"
        msg_path = recipient_inbox / msg_filename
        
        # Copy message for each recipient
        msg_copy = msg.copy()
        msg_copy["delivered_to_agent"] = r
        
        with open(msg_path, "w") as f:
            json.dump(msg_copy, f, indent=2)
        
        delivered_to.append(str(msg_path))
    
    return delivered_to

def move_to_delivered(msg):
    """Move update from update queue to delivered."""
    src = Path(msg["_file"])
    delivered_dir = QUEUE_DIR / "delivered"
    delivered_dir.mkdir(parents=True, exist_ok=True)
    dst = delivered_dir / src.name
    shutil.move(str(src), str(dst))
    return dst

def move_to_dead_letter(msg, reason):
    """Move failed update to dead letter queue."""
    DEAD_LETTER_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(msg["_file"])
    dst = DEAD_LETTER_DIR / src.name
    
    msg["dead_letter_reason"] = reason
    msg["dead_letter_time"] = now_iso()
    
    with open(dst, "w") as f:
        json.dump(msg, f, indent=2)
    
    src.unlink()
    return dst

# ── Main Worker Loop ─────────────────────────────────────────────────

def run_update_courier():
    """Main update courier loop.
    
    ONLY delivers updates.
    """
    print(f"[{now_iso()}] Update Courier started")
    print(f"  Handles: update")
    print(f"  Ignores: message, request, reply")
    print(f"  Check interval: {CHECK_INTERVAL}s")
    print(f"  Max retries: {MAX_RETRIES}")
    
    while True:
        try:
            updates = get_pending_updates()
            
            if not updates:
                time.sleep(CHECK_INTERVAL)
                continue
            
            print(f"[{now_iso()}] Found {len(updates)} updates to deliver")
            
            for msg in updates:
                msg_id = msg["id"]
                recipient = msg["recipient"]
                retries = msg.get("retries", 0)
                
                # Check retry limit
                if retries >= MAX_RETRIES:
                    print(f"  [{msg_id}] Max retries reached, moving to dead letter")
                    move_to_dead_letter(msg, "Max retries exceeded")
                    log_audit({
                        "event": "dead_letter",
                        "msg_id": msg_id,
                        "msg_type": "update",
                        "recipient": recipient,
                        "reason": "Max retries exceeded",
                        "timestamp": now_iso()
                    })
                    continue
                
                # Update state
                msg["state"] = "in_transit"
                msg["picked_up_at"] = now_iso()
                msg["picked_up_by"] = "update_courier"
                msg["retries"] = retries + 1
                
                print(f"  [{msg_id}] Picked up update, delivering to {recipient}")
                
                # Deliver
                try:
                    delivered_to = deliver_update(msg)
                    
                    # Update state to delivered
                    msg["state"] = "delivered"
                    msg["delivered_at"] = now_iso()
                    msg["delivered_to"] = delivered_to
                    
                    # Move to delivered queue
                    move_to_delivered(msg)
                    
                    print(f"  [{msg_id}] Delivered to {len(delivered_to)} recipients")
                    
                    log_audit({
                        "event": "update_delivered",
                        "msg_id": msg_id,
                        "msg_type": "update",
                        "sender": msg["sender"],
                        "recipient": recipient,
                        "delivered_at": msg["delivered_at"],
                        "delivered_to": delivered_to
                    })
                    
                except Exception as e:
                    print(f"  [{msg_id}] Delivery failed: {e}")
                    msg["state"] = "pending_update"
                    msg["last_error"] = str(e)
                    msg["error_time"] = now_iso()
                    
                    # Save back to queue
                    with open(msg["_file"], "w") as f:
                        json.dump(msg, f, indent=2)
                    
                    log_audit({
                        "event": "update_delivery_failed",
                        "msg_id": msg_id,
                        "error": str(e),
                        "timestamp": now_iso()
                    })
            
        except Exception as e:
            print(f"[{now_iso()}] Worker error: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    run_update_courier()
