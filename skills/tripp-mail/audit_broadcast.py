"""Tripp.Mail — Audit Broadcast System

Sends audit requests to ALL agents and collects all responses.
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
AUDIT_RESPONSES_DIR = BASE_DIR / "audit" / "responses"

ALL_AGENTS = ["echo", "tripp", "cyony", "kimi", "codex"]

# ── Helpers ───────────────────────────────────────────────────────────

def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"

def log_audit(event):
    """Append event to audit trail."""
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_file = AUDIT_DIR / "audit.jsonl"
    with open(audit_file, "a") as f:
        f.write(json.dumps(event) + "\n")

def create_audit_request(project_name, description, eddie_instructions):
    """Create an audit request and send to all agents."""
    
    audit_id = f"audit_{int(datetime.datetime.utcnow().timestamp())}_{project_name}"
    
    # Create audit request
    audit_request = {
        "id": audit_id,
        "type": "audit_request",
        "project_name": project_name,
        "description": description,
        "eddie_instructions": eddie_instructions,
        "created_at": now_iso(),
        "created_by": "eddie",
        "status": "collecting_responses",
        "responded_by": [],
    }
    
    # Save audit request
    audit_requests_dir = BASE_DIR / "audit" / "requests"
    audit_requests_dir.mkdir(parents=True, exist_ok=True)
    
    request_path = audit_requests_dir / f"{audit_id}.json"
    with open(request_path, "w") as f:
        json.dump(audit_request, f, indent=2)
    
    # Create message for each agent
    for agent in ALL_AGENTS:
        msg = {
            "id": f"{audit_id}_{agent}",
            "type": "audit_request",
            "audit_id": audit_id,
            "sender": "eddie",
            "recipient": agent,
            "project_name": project_name,
            "description": description,
            "eddie_instructions": eddie_instructions,
            "content": f"AUDIT REQUEST: {project_name}\n\n{description}\n\nEddie's Instructions: {eddie_instructions}\n\nPlease review and provide your feedback. Reply to this message with your thoughts.",
            "state": "pending_delivery",
            "created_at": now_iso(),
            "retries": 0,
        }
        
        # Add to delivery queue
        delivery_dir = QUEUE_DIR / "delivery"
        delivery_dir.mkdir(parents=True, exist_ok=True)
        
        msg_path = delivery_dir / f"{audit_id}_{agent}.json"
        with open(msg_path, "w") as f:
            json.dump(msg, f, indent=2)
    
    log_audit({
        "event": "audit_request_created",
        "audit_id": audit_id,
        "project_name": project_name,
        "agents_notified": ALL_AGENTS,
        "timestamp": now_iso()
    })
    
    return audit_id

def collect_audit_response(audit_id, agent, response):
    """Collect an agent's audit response."""
    
    AUDIT_RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    
    response_data = {
        "audit_id": audit_id,
        "agent": agent,
        "response": response,
        "timestamp": now_iso(),
    }
    
    # Save response
    response_path = AUDIT_RESPONSES_DIR / f"{audit_id}_{agent}.json"
    with open(response_path, "w") as f:
        json.dump(response_data, f, indent=2)
    
    # Update audit request
    request_path = BASE_DIR / "audit" / "requests" / f"{audit_id}.json"
    if request_path.exists():
        with open(request_path) as f:
            audit_request = json.load(f)
        
        if agent not in audit_request["responded_by"]:
            audit_request["responded_by"].append(agent)
        
        # Check if all agents have responded
        if len(audit_request["responded_by"]) == len(ALL_AGENTS):
            audit_request["status"] = "all_responses_collected"
        else:
            audit_request["status"] = f"collecting_responses ({len(audit_request['responded_by'])}/{len(ALL_AGENTS)})"
        
        with open(request_path, "w") as f:
            json.dump(audit_request, f, indent=2)
    
    log_audit({
        "event": "audit_response_received",
        "audit_id": audit_id,
        "agent": agent,
        "timestamp": now_iso()
    })
    
    return response_path

def get_audit_status(audit_id):
    """Get status of an audit request."""
    request_path = BASE_DIR / "audit" / "requests" / f"{audit_id}.json"
    if not request_path.exists():
        return None
    
    with open(request_path) as f:
        return json.load(f)

def get_all_responses(audit_id):
    """Get all responses for an audit."""
    AUDIT_RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    
    responses = []
    for response_file in AUDIT_RESPONSES_DIR.glob(f"{audit_id}_*.json"):
        with open(response_file) as f:
            responses.append(json.load(f))
    
    return responses

# ── CLI ───────────────────────────────────────────────────────────────

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Tripp.Mail Audit Broadcast")
    parser.add_argument("action", choices=["create", "status", "responses", "respond"])
    parser.add_argument("--audit-id", help="Audit ID")
    parser.add_argument("--project", help="Project name")
    parser.add_argument("--description", help="Project description")
    parser.add_argument("--instructions", help="Eddie's instructions")
    parser.add_argument("--agent", help="Agent name")
    parser.add_argument("--response", help="Agent's response")
    
    args = parser.parse_args()
    
    if args.action == "create":
        if not args.project or not args.description or not args.instructions:
            print("Error: --project, --description, and --instructions required")
            return
        
        audit_id = create_audit_request(args.project, args.description, args.instructions)
        print(f"Audit request created: {audit_id}")
        print(f"Sent to: {', '.join(ALL_AGENTS)}")
    
    elif args.action == "status":
        if not args.audit_id:
            print("Error: --audit-id required")
            return
        
        status = get_audit_status(args.audit_id)
        if status:
            print(json.dumps(status, indent=2))
        else:
            print(f"Audit {args.audit_id} not found")
    
    elif args.action == "responses":
        if not args.audit_id:
            print("Error: --audit-id required")
            return
        
        responses = get_all_responses(args.audit_id)
        print(f"Responses ({len(responses)}/{len(ALL_AGENTS)}):")
        for resp in responses:
            print(f"\n  {resp['agent']}:")
            print(f"  {resp['response'][:200]}...")
    
    elif args.action == "respond":
        if not args.audit_id or not args.agent or not args.response:
            print("Error: --audit-id, --agent, and --response required")
            return
        
        response_path = collect_audit_response(args.audit_id, args.agent, args.response)
        print(f"Response saved: {response_path}")

if __name__ == "__main__":
    main()
