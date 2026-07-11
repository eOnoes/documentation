"""Tripp.Mail — Delivery Courier Worker (v3)

Reads chain of custody from message and delivers to correct recipient.
Only handles messages, requests, and audit_requests.
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
MESSAGES_DIR = BASE_DIR / "messages"
DEAD_LETTER_DIR = QUEUE_DIR / "dead"

MAX_RETRIES = 3
DELIVERY_TIMEOUT = 300  # 5 minutes
CHECK_INTERVAL = 30  # seconds

# ── Message Types This Worker Handles ─────────────────────────────────

# THIS WORKER ONLY HANDLES:
#   - "message"        (direct message between agents)
#   - "request"        (request for action)
#   - "audit_request"  (audit review request)
#
# THIS WORKER DOES NOT HANDLE:
#   - "reply"    (handled by reply_worker.py)
#   - "update"   (handled by update_worker.py)

# ── Helpers ───────────────────────────────────────────────────────────

def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"

def log_audit(event):
    """Append event to audit trail."""
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_file = AUDIT_DIR / "audit.jsonl"
    with open(audit_file, "a") as f:
        f.write(json.dumps(event) + "\n")

def get_pending_messages():
    """Get messages waiting for delivery.
    
    Reads from delivery queue AND messages directory.
    """
    messages = []
    
    # Check delivery queue
    delivery_dir = QUEUE_DIR / "delivery"
    if delivery_dir.exists():
        for msg_file in sorted(delivery_dir.glob("*.json")):
            try:
                with open(msg_file) as f:
                    msg = json.load(f)
                
                # Only handle our types
                msg_type = msg.get("type", "")
                if msg_type not in ("message", "request", "audit_request"):
                    continue
                
                msg["_file"] = str(msg_file)
                messages.append(msg)
            except Exception as e:
                print(f"Error reading {msg_file}: {e}")
    
    # Check messages directory
    if MESSAGES_DIR.exists():
        for msg_file in sorted(MESSAGES_DIR.glob("*.json")):
            try:
                with open(msg_file) as f:
                    msg = json.load(f)
                
                # Only handle pending messages
                if msg.get("state") != "pending_delivery":
                    continue
                
                # Only handle our types
                msg_type = msg.get("type", "")
                if msg_type not in ("message", "request", "audit_request"):
                    continue
                
                msg["_file"] = str(msg_file)
                messages.append(msg)
            except Exception as e:
                print(f"Error reading {msg_file}: {e}")
    
    return messages

def deliver_message(msg):
    """Deliver message to recipient.
    
    If recipient is "all", deliver to all agents.
    If recipient is a specific agent, deliver to that agent.
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
        
        # Create message file
        msg_filename = f"{msg['id']}.json"
        msg_path = recipient_inbox / msg_filename
        
        # Copy message for each recipient
        msg_copy = msg.copy()
        msg_copy["delivered_to_agent"] = r
        msg_copy["delivered_at"] = now_iso()
        
        with open(msg_path, "w") as f:
            json.dump(msg_copy, f, indent=2)
        
        delivered_to.append(str(msg_path))
    
    return delivered_to

def move_to_delivered(msg):
    """Move message from queue to delivered."""
    src = Path(msg["_file"])
    delivered_dir = QUEUE_DIR / "delivered"
    delivered_dir.mkdir(parents=True, exist_ok=True)
    dst = delivered_dir / src.name
    shutil.move(str(src), str(dst))
    return dst

def move_to_dead_letter(msg, reason):
    """Move failed message to dead letter queue."""
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

def run_delivery_courier():
    """Main delivery courier loop.
    
    Handles: message, request, audit_request
    """
    print(f"[{now_iso()}] Delivery Courier started")
    print(f"  Handles: message, request, audit_request")
    print(f"  Ignores: reply, update")
    print(f"  Check interval: {CHECK_INTERVAL}s")
    print(f"  Max retries: {MAX_RETRIES}")
    
    while True:
        try:
            messages = get_pending_messages()
            
            if not messages:
                time.sleep(CHECK_INTERVAL)
                continue
            
            print(f"[{now_iso()}] Found {len(messages)} messages to deliver")
            
            for msg in messages:
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
                        "msg_type": msg.get("type"),
                        "recipient": recipient,
                        "reason": "Max retries exceeded",
                        "timestamp": now_iso()
                    })
                    continue
                
                # Update state
                msg["state"] = "in_transit"
                msg["picked_up_at"] = now_iso()
                msg["picked_up_by"] = "delivery_courier"
                msg["retries"] = retries + 1
                
                print(f"  [{msg_id}] Picked up {msg.get('type')}, delivering to {recipient}")
                
                # Deliver
                try:
                    delivered_to = deliver_message(msg)
                    
                    # Update state to delivered
                    msg["state"] = "delivered"
                    msg["delivered_at"] = now_iso()
                    msg["delivered_to"] = delivered_to
                    
                    # Move to delivered queue
                    move_to_delivered(msg)
                    
                    print(f"  [{msg_id}] Delivered to {len(delivered_to)} recipients")
                    
                    log_audit({
                        "event": "delivered",
                        "msg_id": msg_id,
                        "msg_type": msg.get("type"),
                        "sender": msg["sender"],
                        "recipient": recipient,
                        "delivered_at": msg["delivered_at"],
                        "delivered_to": delivered_to,
                        "chain_step": msg.get("chain", {}).get("current_step", 0)
                    })
                    
                except Exception as e:
                    print(f"  [{msg_id}] Delivery failed: {e}")
                    msg["state"] = "pending_delivery"
                    msg["last_error"] = str(e)
                    msg["error_time"] = now_iso()
                    
                    # Save back to queue
                    with open(msg["_file"], "w") as f:
                        json.dump(msg, f, indent=2)
                    
                    log_audit({
                        "event": "delivery_failed",
                        "msg_id": msg_id,
                        "error": str(e),
                        "timestamp": now_iso()
                    })
            
        except Exception as e:
            print(f"[{now_iso()}] Worker error: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    run_delivery_courier()
