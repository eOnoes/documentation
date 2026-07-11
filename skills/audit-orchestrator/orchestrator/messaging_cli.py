"""Messaging CLI — Agent Interface"""

import sys
import json
import argparse
import os
from datetime import datetime

from .messaging_engine import MessagingEngine
from .messaging_config import MESSAGING_DIR, KILL_SWITCH_FILE


def main():
    parser = argparse.ArgumentParser(description="Agent Messaging System")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # Send
    send = subparsers.add_parser("send", help="Send message")
    send.add_argument("sender")
    send.add_argument("recipient")
    send.add_argument("content")
    send.add_argument("--type", default="request", choices=["request", "discussion", "task", "status"])

    # Reply
    reply = subparsers.add_parser("reply", help="Reply")
    reply.add_argument("thread_id")
    reply.add_argument("agent")
    reply.add_argument("content")

    # List
    lst = subparsers.add_parser("list", help="List threads")
    lst.add_argument("--status")
    lst.add_argument("--agent")

    # Status
    stat = subparsers.add_parser("status", help="Thread status")
    stat.add_argument("thread_id")

    # Kill
    kill = subparsers.add_parser("kill", help="Kill thread")
    kill.add_argument("thread_id")
    kill.add_argument("--reason", default="Manual kill")

    # Timeouts
    subparsers.add_parser("check-timeouts", help="Check timeouts")

    # Kill switch
    ks = subparsers.add_parser("kill-switch", help="Kill switch")
    ks.add_argument("action", choices=["activate", "deactivate", "status"])

    args = parser.parse_args()
    engine = MessagingEngine()
    engine._load_threads()

    if args.command == "send":
        result = engine.create_thread(args.sender, args.recipient, args.content, args.type)
    elif args.command == "reply":
        result = engine.add_response(args.thread_id, args.agent, args.content)
    elif args.command == "list":
        result = engine.list_threads(args.status)
        if args.agent:
            result["threads"] = [t for t in result["threads"] if args.agent in t["participants"]]
            result["count"] = len(result["threads"])
    elif args.command == "status":
        result = engine.get_thread(args.thread_id)
    elif args.command == "kill":
        result = engine.kill_thread(args.thread_id, args.reason)
    elif args.command == "check-timeouts":
        result = {"timed_out": engine.check_timeouts()}
    elif args.command == "kill-switch":
        if args.action == "activate":
            with open(KILL_SWITCH_FILE, "w") as f:
                f.write("Activated at {}".format(datetime.utcnow().isoformat()))
            result = {"status": "activated"}
        elif args.action == "deactivate":
            if os.path.exists(KILL_SWITCH_FILE):
                os.remove(KILL_SWITCH_FILE)
            result = {"status": "deactivated"}
        else:
            result = {"active": os.path.exists(KILL_SWITCH_FILE)}
    else:
        parser.print_help()
        return

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
