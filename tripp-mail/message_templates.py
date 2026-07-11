#!/usr/bin/env python3
"""
Tripp.Mail — Message Template System

Creates standardized message/reply templates with explicit fields
that workers read to know WHERE to deliver next.
"""

import os
import json
import datetime
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────

BASE_DIR = Path("/opt/data/shared/tripp-mail")
TEMPLATES_DIR = BASE_DIR / "templates"
MESSAGES_DIR = BASE_DIR / "messages"

# ── Message Template ──────────────────────────────────────────────────

def create_message_template():
    """Create a blank message template with explicit fields."""
    return {
        # ── Required Fields ──
        "id": "",                    # Unique message ID
        "type": "",                  # "message", "reply", "audit_request", "update"
        
        # ── Sender/Recipient ──
        "sender": "",                # Who sent this
        "recipient": "",             # Who this is FOR (or "all" for broadcasts)
        
        # ── Content ──
        "subject": "",               # Brief subject line
        "content": "",               # Actual message content
        "instructions": "",          # What the recipient should do
        
        # ── Chain of Custody ──
        "chain": {
            "current_step": 0,       # Which step we're on
            "steps": [],             # List of steps (see below)
            "history": []            # Audit trail of who did what
        },
        
        # ── Status ──
        "state": "pending_delivery", # Current state
        "created_at": "",            # When created
        "updated_at": "",            # When last updated
        
        # ── Metadata ──
        "project": "",               # Which project this belongs to
        "thread_id": "",             # Thread for grouping related messages
        "priority": "normal",        # "low", "normal", "high", "urgent"
        "retries": 0,                # Delivery retry count
        "max_retries": 3,            # Max retries before dead letter
    }

# ── Chain Steps ───────────────────────────────────────────────────────

def create_audit_chain(lead, reviewers, final_recipient):
    """Create a chain for an audit review process.
    
    Example:
        chain = create_audit_chain(
            lead="codex",
            reviewers=["echo", "tripp"],
            final_recipient="eddie"
        )
    
    This creates:
        Step 0: Lead creates audit → deliver to Echo
        Step 1: Echo reviews → deliver to Tripp
        Step 2: Tripp reviews → deliver to Lead
        Step 3: Lead incorporates → deliver to final_recipient
    """
    steps = []
    
    # Step 0: Lead sends to first reviewer
    steps.append({
        "step": 0,
        "action": "deliver_to_reviewer",
        "from": lead,
        "to": reviewers[0],
        "instruction": f"Review this audit and provide your feedback. When done, update 'chain.current_step' to {1} and set 'recipient' to '{reviewers[1] if len(reviewers) > 1 else lead}'."
    })
    
    # Steps 1-N-1: Each reviewer passes to next
    for i in range(1, len(reviewers)):
        steps.append({
            "step": i,
            "action": "deliver_to_reviewer",
            "from": reviewers[i-1],
            "to": reviewers[i],
            "instruction": f"Review this audit and provide your feedback. When done, update 'chain.current_step' to {i+1} and set 'recipient' to '{lead}'."
        })
    
    # Final step: Back to lead, then to final recipient
    steps.append({
        "step": len(reviewers),
        "action": "deliver_to_lead",
        "from": reviewers[-1],
        "to": lead,
        "instruction": f"Incorporate all feedback. Then update 'chain.current_step' to {len(reviewers)+1} and set 'recipient' to '{final_recipient}'."
    })
    
    steps.append({
        "step": len(reviewers) + 1,
        "action": "deliver_final",
        "from": lead,
        "to": final_recipient,
        "instruction": "Final version ready for build. Process complete."
    })
    
    return {
        "current_step": 0,
        "steps": steps,
        "history": []
    }

def create_simple_chain(sender, recipient):
    """Create a simple 2-step chain (send → reply)."""
    return {
        "current_step": 0,
        "steps": [
            {
                "step": 0,
                "action": "deliver",
                "from": sender,
                "to": recipient,
                "instruction": f"Process this message. When done, update 'chain.current_step' to 1 and set 'recipient' to '{sender}'."
            },
            {
                "step": 1,
                "action": "reply",
                "from": recipient,
                "to": sender,
                "instruction": "Reply delivered. Process complete."
            }
        ],
        "history": []
    }

# ── Message Creation ──────────────────────────────────────────────────

def create_message(msg_type, sender, recipient, subject, content, instructions, chain=None):
    """Create a new message with all required fields filled."""
    template = create_message_template()
    
    msg_id = f"{msg_type}_{int(datetime.datetime.utcnow().timestamp())}_{sender}_{recipient}"
    
    template["id"] = msg_id
    template["type"] = msg_type
    template["sender"] = sender
    template["recipient"] = recipient
    template["subject"] = subject
    template["content"] = content
    template["instructions"] = instructions
    template["created_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    template["updated_at"] = template["created_at"]
    template["state"] = "pending_delivery"
    
    if chain:
        template["chain"] = chain
    else:
        template["chain"] = create_simple_chain(sender, recipient)
    
    return template

def create_audit_request(lead, reviewers, subject, content, instructions):
    """Create an audit request with full chain of custody."""
    
    # Create the chain
    chain = create_audit_chain(
        lead=lead,
        reviewers=reviewers,
        final_recipient=lead  # Lead gets final version
    )
    
    # Create message to first reviewer
    msg = create_message(
        msg_type="audit_request",
        sender=lead,
        recipient=reviewers[0],
        subject=subject,
        content=content,
        instructions=instructions,
        chain=chain
    )
    
    # Add audit-specific fields
    msg["audit"] = {
        "lead": lead,
        "reviewers": reviewers,
        "current_reviewer": 0,
        "total_reviewers": len(reviewers),
        "responses": {}
    }
    
    return msg

def advance_chain(msg, agent, action="reviewed"):
    """Advance the chain to the next step.
    
    This is called when an agent finishes their part.
    """
    chain = msg["chain"]
    current_step = chain["current_step"]
    
    # Record history
    chain["history"].append({
        "step": current_step,
        "agent": agent,
        "action": action,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    })
    
    # Advance to next step
    next_step = current_step + 1
    if next_step < len(chain["steps"]):
        chain["current_step"] = next_step
        next_step_info = chain["steps"][next_step]
        
        # Update recipient to next person in chain
        msg["recipient"] = next_step_info["to"]
        msg["instructions"] = next_step_info["instruction"]
        msg["state"] = "pending_delivery"
        msg["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        
        return True, next_step_info["to"]
    else:
        # Chain complete
        msg["state"] = "complete"
        msg["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        return False, None

def get_chain_status(msg):
    """Get human-readable chain status."""
    chain = msg["chain"]
    current_step = chain["current_step"]
    steps = chain["steps"]
    
    if current_step >= len(steps):
        return "COMPLETE"
    
    step_info = steps[current_step]
    return f"Step {current_step + 1}/{len(steps)}: {step_info['from']} → {step_info['to']}"

# ── CLI ───────────────────────────────────────────────────────────────

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Tripp.Mail Message Templates")
    parser.add_argument("action", choices=["create", "advance", "status"])
    parser.add_argument("--type", help="Message type")
    parser.add_argument("--sender", help="Sender")
    parser.add_argument("--recipient", help="Recipient")
    parser.add_argument("--subject", help="Subject")
    parser.add_argument("--content", help="Content")
    parser.add_argument("--instructions", help="Instructions")
    parser.add_argument("--lead", help="Audit lead")
    parser.add_argument("--reviewers", nargs="+", help="Audit reviewers")
    parser.add_argument("--agent", help="Agent advancing chain")
    parser.add_argument("--msg-file", help="Message file to advance")
    
    args = parser.parse_args()
    
    if args.action == "create":
        if args.lead and args.reviewers:
            # Audit request
            msg = create_audit_request(
                lead=args.lead,
                reviewers=args.reviewers,
                subject=args.subject or "Audit Request",
                content=args.content or "",
                instructions=args.instructions or "Please review and provide feedback."
            )
        else:
            # Simple message
            msg = create_message(
                msg_type=args.type or "message",
                sender=args.sender,
                recipient=args.recipient,
                subject=args.subject or "",
                content=args.content or "",
                instructions=args.instructions or ""
            )
        
        # Save message
        MESSAGES_DIR.mkdir(parents=True, exist_ok=True)
        msg_path = MESSAGES_DIR / f"{msg['id']}.json"
        with open(msg_path, "w") as f:
            json.dump(msg, f, indent=2)
        
        print(f"Message created: {msg['id']}")
        print(f"Chain: {get_chain_status(msg)}")
        print(f"To: {msg['recipient']}")
    
    elif args.action == "advance":
        if not args.msg_file or not args.agent:
            print("Error: --msg-file and --agent required")
            return
        
        # Load message
        msg_path = MESSAGES_DIR / args.msg_file
        if not msg_path.exists():
            print(f"Message not found: {args.msg_file}")
            return
        
        with open(msg_path) as f:
            msg = json.load(f)
        
        # Advance chain
        has_next, next_recipient = advance_chain(msg, args.agent)
        
        # Save updated message
        with open(msg_path, "w") as f:
            json.dump(msg, f, indent=2)
        
        if has_next:
            print(f"Chain advanced. Next: {next_recipient}")
            print(f"Status: {get_chain_status(msg)}")
        else:
            print("Chain complete!")
    
    elif args.action == "status":
        if not args.msg_file:
            print("Error: --msg-file required")
            return
        
        # Load message
        msg_path = MESSAGES_DIR / args.msg_file
        if not msg_path.exists():
            print(f"Message not found: {args.msg_file}")
            return
        
        with open(msg_path) as f:
            msg = json.load(f)
        
        print(f"Status: {get_chain_status(msg)}")
        print(f"State: {msg['state']}")
        print(f"Recipient: {msg['recipient']}")
        print(f"Instructions: {msg['instructions']}")
        print(f"\nChain History:")
        for h in msg["chain"]["history"]:
            print(f"  Step {h['step']}: {h['agent']} {h['action']} at {h['timestamp']}")

if __name__ == "__main__":
    main()
