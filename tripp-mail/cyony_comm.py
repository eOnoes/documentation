#!/usr/bin/env python3
"""
Cyony's Communication Script

Simple interface for Cyony to check inbox and send messages.
Run from OpenClaw via SSH: ssh vps "python3 /opt/data/shared/tripp-mail/cyony_comm.py check"
"""

import os
import sys
import json
import subprocess
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────────

BASE_DIR = "/opt/data/shared/tripp-mail"
INBOX_DIR = f"{BASE_DIR}/inbox/cyony"
AUDIT_DIR = f"{BASE_DIR}/audit"

# ── Helpers ───────────────────────────────────────────────────────────

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def run_command(cmd):
    """Run shell command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout.strip()

# ── Commands ──────────────────────────────────────────────────────────

def check_inbox():
    """Check for new messages in inbox."""
    if not os.path.exists(INBOX_DIR):
        print("No messages")
        return
    
    files = sorted([f for f in os.listdir(INBOX_DIR) if f.endswith('.json')])
    
    if not files:
        print("No messages")
        return
    
    print(f"You have {len(files)} message(s):")
    print()
    
    for f in files:
        path = os.path.join(INBOX_DIR, f)
        with open(path) as fh:
            msg = json.load(fh)
        
        msg_type = msg.get('type', 'unknown')
        sender = msg.get('sender', 'unknown')
        content = msg.get('content', 'No content')
        created = msg.get('created_at', 'unknown')
        
        print(f"  [{msg_type.upper()}] From: {sender}")
        print(f"  Time: {created}")
        print(f"  Message: {content[:100]}...")
        print()

def read_message(msg_id):
    """Read a specific message."""
    path = os.path.join(INBOX_DIR, f"{msg_id}.json")
    if not os.path.exists(path):
        print(f"Message {msg_id} not found")
        return
    
    with open(path) as f:
        msg = json.load(f)
    
    print(json.dumps(msg, indent=2))

def send_reply(thread_id, content):
    """Send a reply to a message."""
    cmd = f"""python3 {BASE_DIR}/tripp_mail.py reply \
        --sender cyony \
        --recipient {get_sender(thread_id)} \
        --thread-id {thread_id} \
        --message "{content}" """
    
    output = run_command(cmd)
    print(output)

def send_message(recipient, content):
    """Send a new message."""
    cmd = f"""python3 {BASE_DIR}/tripp_mail.py send \
        --sender cyony \
        --recipient {recipient} \
        --message "{content}" """
    
    output = run_command(cmd)
    print(output)

def get_sender(thread_id):
    """Get sender from thread ID."""
    # Parse thread ID to get sender
    # Format: msg_timestamp_sender_recipient
    parts = thread_id.split('_')
    if len(parts) >= 3:
        return parts[-2]  # sender is second to last
    return "echo"  # default

def check_audit():
    """Check recent audit events."""
    audit_file = f"{AUDIT_DIR}/audit.jsonl"
    if not os.path.exists(audit_file):
        print("No audit events")
        return
    
    with open(audit_file) as f:
        lines = f.readlines()
    
    # Get last 10 events
    recent = lines[-10:] if len(lines) > 10 else lines
    
    print(f"Recent audit events ({len(recent)}):")
    for line in recent:
        event = json.loads(line)
        print(f"  {event.get('timestamp', 'unknown')} - {event.get('event', 'unknown')}: {event.get('msg_id', 'unknown')}")

def status():
    """Check Tripp-Mail status."""
    cmd = f"python3 {BASE_DIR}/tripp_mail.py status"
    output = run_command(cmd)
    print(output)

# ── Main ──────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: cyony_comm.py <command> [args]")
        print()
        print("Commands:")
        print("  check              - Check inbox for new messages")
        print("  read <msg_id>      - Read a specific message")
        print("  reply <thread_id> <content> - Reply to a message")
        print("  send <recipient> <content>  - Send a new message")
        print("  audit              - Check recent audit events")
        print("  status             - Check Tripp-Mail status")
        return
    
    command = sys.argv[1]
    
    if command == "check":
        check_inbox()
    elif command == "read":
        if len(sys.argv) < 3:
            print("Usage: cyony_comm.py read <msg_id>")
            return
        read_message(sys.argv[2])
    elif command == "reply":
        if len(sys.argv) < 4:
            print("Usage: cyony_comm.py reply <thread_id> <content>")
            return
        send_reply(sys.argv[2], sys.argv[3])
    elif command == "send":
        if len(sys.argv) < 4:
            print("Usage: cyony_comm.py send <recipient> <content>")
            return
        send_message(sys.argv[2], sys.argv[3])
    elif command == "audit":
        check_audit()
    elif command == "status":
        status()
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
