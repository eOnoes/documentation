"""Tripp.Mail — Main Runner

Starts all three couriers and manages the system.
"""

import os
import sys
import json
import time
import signal
import datetime
import threading
from pathlib import Path

# Add workers to path
sys.path.insert(0, str(Path(__file__).parent / "workers"))

from delivery_worker import run_delivery_courier
from reply_worker import run_reply_courier
from update_worker import run_update_courier

# ── Configuration ─────────────────────────────────────────────────────

BASE_DIR = Path("/opt/data/shared/tripp-mail")
CONFIG_FILE = BASE_DIR / "config.json"
PID_FILE = BASE_DIR / "tripp-mail.pid"
KILL_SWITCH = BASE_DIR / "KILL_SWITCH"

# ── Signal Handling ───────────────────────────────────────────────────

def signal_handler(signum, frame):
    print(f"\n[{now_iso()}] Received signal {signum}, shutting down...")
    cleanup()
    sys.exit(0)

def cleanup():
    """Clean up PID file."""
    if PID_FILE.exists():
        PID_FILE.unlink()

# ── Helpers ───────────────────────────────────────────────────────────

def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"

def load_config():
    """Load system configuration."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {
        "enabled_agents": ["echo", "tripp", "cyony", "kimi", "codex"],
        "max_messages_per_agent": 10,
        "delivery_timeout": 300,
        "max_retries": 3,
        "check_interval": 30,
    }

def check_kill_switch():
    """Check if kill switch is activated."""
    return KILL_SWITCH.exists()

def create_directories():
    """Create all required directories."""
    dirs = [
        BASE_DIR / "inbox" / "echo",
        BASE_DIR / "inbox" / "tripp",
        BASE_DIR / "inbox" / "cyony",
        BASE_DIR / "inbox" / "kimi",
        BASE_DIR / "inbox" / "codex",
        BASE_DIR / "queue" / "delivery",
        BASE_DIR / "queue" / "reply",
        BASE_DIR / "queue" / "update",
        BASE_DIR / "queue" / "delivered",
        BASE_DIR / "queue" / "dead",
        BASE_DIR / "audit",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

def write_pid():
    """Write PID file."""
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

def get_status():
    """Get system status."""
    config = load_config()
    
    # Count messages in queues
    delivery_queue = BASE_DIR / "queue" / "delivery"
    reply_queue = BASE_DIR / "queue" / "reply"
    update_queue = BASE_DIR / "queue" / "update"
    
    delivery_count = len(list(delivery_queue.glob("*.json"))) if delivery_queue.exists() else 0
    reply_count = len(list(reply_queue.glob("*.json"))) if reply_queue.exists() else 0
    update_count = len(list(update_queue.glob("*.json"))) if update_queue.exists() else 0
    
    # Check audit log
    audit_file = BASE_DIR / "audit" / "audit.jsonl"
    audit_count = 0
    if audit_file.exists():
        with open(audit_file) as f:
            audit_count = sum(1 for _ in f)
    
    # Check kill switch
    kill_switch_active = check_kill_switch()
    
    # Check PID
    pid = None
    running = False
    if PID_FILE.exists():
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        # Check if process is running
        try:
            os.kill(pid, 0)
            running = True
        except OSError:
            running = False
    
    return {
        "status": "running" if running else "stopped",
        "pid": pid,
        "running": running,
        "kill_switch": kill_switch_active,
        "delivery_queue": delivery_count,
        "reply_queue": reply_count,
        "update_queue": update_count,
        "audit_events": audit_count,
        "config": config,
    }

# ── Main ──────────────────────────────────────────────────────────────

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Tripp.Mail — Message Courier System")
    parser.add_argument("action", choices=["start", "stop", "status", "kill-switch", "send", "reply", "update"])
    parser.add_argument("--sender", help="Sender agent name")
    parser.add_argument("--recipient", help="Recipient agent name")
    parser.add_argument("--message", help="Message content")
    parser.add_argument("--reason", default="Manual kill", help="Kill reason")
    parser.add_argument("--thread-id", help="Thread ID for replies")
    parser.add_argument("--subject", help="Update subject")
    
    args = parser.parse_args()
    
    if args.action == "status":
        status = get_status()
        print(json.dumps(status, indent=2))
        return
    
    elif args.action == "kill-switch":
        if KILL_SWITCH.exists():
            KILL_SWITCH.unlink()
            print("Kill switch deactivated")
        else:
            with open(KILL_SWITCH, "w") as f:
                f.write(f"Activated at {now_iso()}")
            print("Kill switch activated")
        return
    
    elif args.action == "send":
        if not args.sender or not args.recipient or not args.message:
            print("Error: --sender, --recipient, and --message required")
            return
        
        # Create message
        msg_id = f"msg_{int(datetime.datetime.utcnow().timestamp())}_{args.sender}_{args.recipient}"
        msg = {
            "id": msg_id,
            "type": "message",  # Explicit type
            "sender": args.sender,
            "recipient": args.recipient,
            "content": args.message,
            "state": "pending_delivery",
            "created_at": now_iso(),
            "retries": 0,
        }
        
        # Add to delivery queue
        delivery_dir = BASE_DIR / "queue" / "delivery"
        delivery_dir.mkdir(parents=True, exist_ok=True)
        
        msg_path = delivery_dir / f"{msg_id}.json"
        with open(msg_path, "w") as f:
            json.dump(msg, f, indent=2)
        
        print(f"Message {msg_id} added to delivery queue")
        return
    
    elif args.action == "reply":
        if not args.sender or not args.recipient or not args.message or not args.thread_id:
            print("Error: --sender, --recipient, --message, and --thread-id required")
            return
        
        # Create reply
        msg_id = f"reply_{int(datetime.datetime.utcnow().timestamp())}_{args.sender}_{args.recipient}"
        msg = {
            "id": msg_id,
            "type": "reply",  # Explicit type
            "thread_id": args.thread_id,
            "sender": args.sender,
            "recipient": args.recipient,
            "content": args.message,
            "state": "pending_reply",
            "created_at": now_iso(),
            "retries": 0,
        }
        
        # Add to reply queue
        reply_dir = BASE_DIR / "queue" / "reply"
        reply_dir.mkdir(parents=True, exist_ok=True)
        
        msg_path = reply_dir / f"{msg_id}.json"
        with open(msg_path, "w") as f:
            json.dump(msg, f, indent=2)
        
        print(f"Reply {msg_id} added to reply queue")
        return
    
    elif args.action == "update":
        if not args.sender or not args.message:
            print("Error: --sender and --message required")
            return
        
        recipient = args.recipient or "all"
        
        # Create update
        msg_id = f"update_{int(datetime.datetime.utcnow().timestamp())}_{args.sender}"
        msg = {
            "id": msg_id,
            "type": "update",  # Explicit type
            "sender": args.sender,
            "recipient": recipient,
            "subject": args.subject or "Status Update",
            "content": args.message,
            "state": "pending_update",
            "created_at": now_iso(),
            "retries": 0,
        }
        
        # Add to update queue
        update_dir = BASE_DIR / "queue" / "update"
        update_dir.mkdir(parents=True, exist_ok=True)
        
        msg_path = update_dir / f"{msg_id}.json"
        with open(msg_path, "w") as f:
            json.dump(msg, f, indent=2)
        
        print(f"Update {msg_id} added to update queue")
        return
    
    elif args.action == "stop":
        if PID_FILE.exists():
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Sent SIGTERM to process {pid}")
            except OSError:
                print(f"Process {pid} not found")
        else:
            print("No PID file found")
        return
    
    elif args.action == "start":
        # Check if already running
        if PID_FILE.exists():
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, 0)
                print(f"Already running (PID {pid})")
                return
            except OSError:
                pass
        
        # Create directories
        create_directories()
        
        # Write PID
        write_pid()
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Load config
        config = load_config()
        check_interval = config.get("check_interval", 30)
        
        print(f"[{now_iso()}] Tripp.Mail starting...")
        print(f"  Delivery Courier: handles message, request")
        print(f"  Reply Courier: handles reply")
        print(f"  Update Courier: handles update")
        print(f"  Check interval: {check_interval}s")
        
        # Start workers in threads
        delivery_thread = threading.Thread(
            target=run_delivery_courier,
            daemon=True,
            name="delivery-courier"
        )
        reply_thread = threading.Thread(
            target=run_reply_courier,
            daemon=True,
            name="reply-courier"
        )
        update_thread = threading.Thread(
            target=run_update_courier,
            daemon=True,
            name="update-courier"
        )
        
        delivery_thread.start()
        reply_thread.start()
        update_thread.start()
        
        print(f"[{now_iso()}] All three couriers started")
        
        # Keep main thread alive
        try:
            while True:
                if check_kill_switch():
                    print(f"[{now_iso()}] Kill switch activated, shutting down...")
                    break
                time.sleep(check_interval)
        except KeyboardInterrupt:
            pass
        finally:
            cleanup()
            print(f"[{now_iso()}] Tripp.Mail stopped")

if __name__ == "__main__":
    main()
