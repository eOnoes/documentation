"""Tripp.Mail — Reply Courier Worker (v3)

Reads chain of custody and delivers replies to correct recipient.
Only handles replies.
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
#   - "reply"  (response to a previous message/request/audit)
#
# THIS WORKER DOES NOT HANDLE:
#   - "message"        (handled by delivery_worker.py)
#   - "request"        (handled by delivery_worker.py)
#   - "audit_request"  (handled by delivery_worker.py)
#   - "update"         (handled by update_worker.py)

# ── Helpers ───────────────────────────────────────────────────────────

def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"

def log_audit(event):
    """Append event to audit trail."""
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_file = AUDIT_DIR / "audit.jsonl"
    with open(audit_file, "a") as f:
        f.write(json.dumps(event) + "\n")

def get_pending_replies():
    """Get replies waiting for delivery.
    
    ONLY picks up messages with type="reply".
    """
    replies = []
    
    # Check reply queue
    reply_dir = QUEUE_DIR / "reply"
    if reply_dir.exists():
        for msg_file in sorted(reply_dir.glob("*.json")):
            try:
                with open(msg_file) as f:
                    msg = json.load(f)
                
                # ONLY handle replies
                msg_type = msg.get("type", "")
                if msg_type != "reply":
                    continue
                
                msg["_file"] = str(msg_file)
                replies.append(msg)
            except Exception as e:
                print(f"Error reading {msg_file}: {e}")
    
    # Check messages directory
    if MESSAGES_DIR.exists():
        for msg_file in sorted(MESSAGES_DIR.glob("*.json")):
            try:
                with open(msg_file) as f:
                    msg = json.load(f)
                
                # Only handle pending replies
                if msg.get("state") != "pending_reply":
                    continue
                
                # ONLY handle replies
                msg_type = msg.get("type", "")
                if msg_type != "reply":
                    continue
                
                msg["_file"] = str(msg_file)
                replies.append(msg)
            except Exception as e:
                print(f"Error reading {msg_file}: {e}")
    
    return replies

def deliver_reply(msg):
    """Deliver reply to recipient.
    
    If recipient has a chain, read the chain to know where to deliver.
    Otherwise, deliver to the recipient field.
    """
    recipient = msg["recipient"]
    
    # Check if there's a chain to follow
    chain = msg.get("chain", {})
    current_step = chain.get("current_step", 0)
    steps = chain.get("steps", [])
    
    if steps and current_step < len(steps):
        # Use chain to determine recipient
        step_info = steps[current_step]
        recipient = step_info["to"]
        msg["recipient"] = recipient
        msg["instructions"] = step_info.get("instruction", "")
    
    # Deliver to recipient's inbox
    recipient_inbox = INBOX_DIR / recipient
    recipient_inbox.mkdir(parents=True, exist_ok=True)
    
    # Create reply file
    msg_filename = f"{msg['id']}.json"
    msg_path = recipient_inbox / msg_filename
    
    with open(msg_path, "w") as f:
        json.dump(msg, f, indent=2)
    
    return msg_path, recipient

def advance_chain(msg, agent):
    """Advance the chain to the next step.
    
    Returns: (has_next, next_recipient)
    """
    chain = msg.get("chain", {})
    current_step = chain.get("current_step", 0)
    steps = chain.get("steps", [])
    history = chain.get("history", [])
    
    # Record this step in history
    history.append({
        "step": current_step,
        "agent": agent,
        "action": "completed",
        "timestamp": now_iso()
    })
    chain["history"] = history
    
    # Advance to next step
    next_step = current_step + 1
    
    if next_step < len(steps):
        chain["current_step"] = next_step
        next_step_info = steps[next_step]
        
        # Update recipient to next person in chain
        msg["recipient"] = next_step_info["to"]
        msg["instructions"] = next_step_info.get("instruction", "")
        msg["state"] = "pending_delivery"
        msg["updated_at"] = now_iso()
        
        return True, next_step_info["to"]
    else:
        # Chain complete
        msg["state"] = "complete"
        msg["updated_at"] = now_iso()
        return False, None

def move_to_delivered(msg):
    """Move reply from reply queue to delivered."""
    src = Path(msg["_file"])
    delivered_dir = QUEUE_DIR / "delivered"
    delivered_dir.mkdir(parents=True, exist_ok=True)
    dst = delivered_dir / src.name
    shutil.move(str(src), str(dst))
    return dst

def move_to_dead_letter(msg, reason):
    """Move failed reply to dead letter queue."""
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

def run_reply_courier():
    """Main reply courier loop.
    
    ONLY delivers replies.
    """
    print(f"[{now_iso()}] Reply Courier started")
    print(f"  Handles: reply")
    print(f"  Ignores: message, request, audit_request, update")
    print(f"  Check interval: {CHECK_INTERVAL}s")
    print(f"  Max retries: {MAX_RETRIES}")
    
    while True:
        try:
            replies = get_pending_replies()
            
            if not replies:
                time.sleep(CHECK_INTERVAL)
                continue
            
            print(f"[{now_iso()}] Found {len(replies)} replies to deliver")
            
            for msg in replies:
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
                        "msg_type": "reply",
                        "recipient": recipient,
                        "reason": "Max retries exceeded",
                        "timestamp": now_iso()
                    })
                    continue
                
                # Update state
                msg["state"] = "in_transit"
                msg["picked_up_at"] = now_iso()
                msg["picked_up_by"] = "reply_courier"
                msg["retries"] = retries + 1
                
                print(f"  [{msg_id}] Picked up reply, delivering to {recipient}")
                
                # Deliver
                try:
                    msg_path, delivered_to = deliver_reply(msg)
                    
                    # Update state to replied
                    msg["state"] = "replied"
                    msg["replied_at"] = now_iso()
                    msg["replied_to"] = str(msg_path)
                    
                    # Move to delivered queue
                    move_to_delivered(msg)
                    
                    print(f"  [{msg_id}] Delivered to {delivered_to}")
                    
                    log_audit({
                        "event": "replied",
                        "msg_id": msg_id,
                        "msg_type": "reply",
                        "sender": msg["sender"],
                        "recipient": delivered_to,
                        "replied_at": msg["replied_at"],
                        "replied_to": str(msg_path),
                        "chain_step": msg.get("chain", {}).get("current_step", 0)
                    })
                    
                except Exception as e:
                    print(f"  [{msg_id}] Delivery failed: {e}")
                    msg["state"] = "pending_reply"
                    msg["last_error"] = str(e)
                    msg["error_time"] = now_iso()
                    
                    # Save back to queue
                    with open(msg["_file"], "w") as f:
                        json.dump(msg, f, indent=2)
                    
                    log_audit({
                        "event": "reply_delivery_failed",
                        "msg_id": msg_id,
                        "error": str(e),
                        "timestamp": now_iso()
                    })
            
        except Exception as e:
            print(f"[{now_iso()}] Worker error: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    run_reply_courier()
