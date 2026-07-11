"""Messaging Engine — Anti-Death-Loop Logic"""

import os
import json
import time
import datetime
import logging
from enum import Enum

from .messaging_config import (
    MAX_ROUNDS, MAX_MESSAGES_PER_THREAD, MAX_DEPTH,
    MESSAGE_TIMEOUT, THREAD_TIMEOUT, COOLDOWN_BETWEEN_MESSAGES,
    MAX_CONCURRENT_THREADS, MAX_MESSAGES_PER_AGENT, AGENT_COOLDOWN,
    MAX_API_CALLS_PER_THREAD, MAX_COST_PER_THREAD,
    KILL_SWITCH_ENABLED, AUTO_KILL_ON_ERROR,
    THREAD_TYPES, THREADS_DIR, KILL_SWITCH_FILE,
)

logger = logging.getLogger(__name__)


class MessagePhase(Enum):
    NEW = "NEW"
    WAITING_FOR_REPLY = "WAITING_FOR_REPLY"
    AGENT_READING = "AGENT_READING"
    AGENT_RESPONDING = "AGENT_RESPONDING"
    RESPONSE_READY = "RESPONSE_READY"
    COMPLETE = "COMPLETE"
    KILLED = "KILLED"
    TIMED_OUT = "TIMED_OUT"
    ERROR = "ERROR"


class MessageThread:
    def __init__(self, thread_id, thread_type="request"):
        self.thread_id = thread_id
        self.thread_type = thread_type
        self.phase = MessagePhase.NEW
        self.messages = []
        self.round = 0
        self.depth = 0
        self.created_at = datetime.datetime.utcnow().isoformat()
        self.updated_at = self.created_at
        self.participants = []
        self.current_agent = None
        self.next_agent = None
        self.error_count = 0
        self.api_calls = 0
        self.cost = 0.0
        self.killed = False
        self.kill_reason = None
        type_config = THREAD_TYPES.get(thread_type, THREAD_TYPES["request"])
        self.max_rounds = type_config["max_rounds"]
        self.timeout = type_config["timeout"]

    def can_add_message(self):
        if self.killed:
            return False, "Thread is killed"
        if self.round >= self.max_rounds:
            return False, "Max rounds reached"
        if len(self.messages) >= MAX_MESSAGES_PER_THREAD:
            return False, "Max messages reached"
        if self.api_calls >= MAX_API_CALLS_PER_THREAD:
            return False, "Max API calls reached"
        if self.cost >= MAX_COST_PER_THREAD:
            return False, "Max cost reached"
        if self.error_count >= AUTO_KILL_ON_ERROR:
            return False, "Too many errors"
        created = datetime.datetime.fromisoformat(self.created_at)
        elapsed = (datetime.datetime.utcnow() - created).total_seconds() / 60
        if elapsed > THREAD_TIMEOUT:
            return False, "Thread timeout exceeded"
        return True, "OK"

    def add_message(self, sender, content, reply_to=None):
        can_add, reason = self.can_add_message()
        if not can_add:
            return {"success": False, "error": reason}
        message = {
            "id": "msg_{}".format(len(self.messages) + 1),
            "sender": sender,
            "content": content,
            "reply_to": reply_to,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }
        self.messages.append(message)
        self.round += 1
        self.updated_at = datetime.datetime.utcnow().isoformat()
        self.api_calls += 1
        self.cost += 0.01
        return {"success": True, "message": message}

    def kill(self, reason="Manual kill"):
        if not KILL_SWITCH_ENABLED:
            return {"success": False, "error": "Kill switch disabled"}
        self.killed = True
        self.kill_reason = reason
        self.phase = MessagePhase.KILLED
        self.updated_at = datetime.datetime.utcnow().isoformat()
        return {"success": True}

    def timeout(self):
        self.phase = MessagePhase.TIMED_OUT
        self.updated_at = datetime.datetime.utcnow().isoformat()
        return {"success": True}

    def error(self, error_msg):
        self.error_count += 1
        self.updated_at = datetime.datetime.utcnow().isoformat()
        if self.error_count >= AUTO_KILL_ON_ERROR:
            self.kill("Auto-killed after {} errors".format(self.error_count))
            return {"killed": True, "error": error_msg}
        return {"killed": False, "error": error_msg}

    def get_status(self):
        return {
            "thread_id": self.thread_id,
            "thread_type": self.thread_type,
            "phase": self.phase.value,
            "round": self.round,
            "max_rounds": self.max_rounds,
            "depth": self.depth,
            "messages_count": len(self.messages),
            "participants": self.participants,
            "current_agent": self.current_agent,
            "next_agent": self.next_agent,
            "error_count": self.error_count,
            "api_calls": self.api_calls,
            "cost": self.cost,
            "killed": self.killed,
            "kill_reason": self.kill_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_dict(self):
        d = self.get_status()
        d["messages"] = self.messages
        d["max_rounds"] = self.max_rounds
        d["timeout"] = self.timeout
        return d

    @classmethod
    def from_dict(cls, data):
        thread = cls(data["thread_id"], data["thread_type"])
        thread.phase = MessagePhase(data["phase"])
        thread.messages = data.get("messages", [])
        thread.round = data.get("round", 0)
        thread.depth = data.get("depth", 0)
        thread.created_at = data.get("created_at", thread.created_at)
        thread.updated_at = data.get("updated_at", thread.updated_at)
        thread.participants = data.get("participants", [])
        thread.current_agent = data.get("current_agent")
        thread.next_agent = data.get("next_agent")
        thread.error_count = data.get("error_count", 0)
        thread.api_calls = data.get("api_calls", 0)
        thread.cost = data.get("cost", 0.0)
        thread.killed = data.get("killed", False)
        thread.kill_reason = data.get("kill_reason")
        thread.max_rounds = data.get("max_rounds", MAX_ROUNDS)
        thread.timeout = data.get("timeout", MESSAGE_TIMEOUT)
        return thread


class MessagingEngine:
    def __init__(self):
        self.threads = {}
        self.agent_message_counts = {}
        self.last_message_times = {}
        os.makedirs(THREADS_DIR, exist_ok=True)

    def _check_kill_switch(self):
        return os.path.exists(KILL_SWITCH_FILE)

    def _check_rate_limit(self, agent):
        now = time.time()
        if agent in self.last_message_times:
            elapsed = now - self.last_message_times[agent]
            if elapsed < AGENT_COOLDOWN:
                return False, "Agent {} on cooldown".format(agent)
        hour_key = int(now // 3600)
        if agent not in self.agent_message_counts:
            self.agent_message_counts[agent] = {}
        current_count = self.agent_message_counts[agent].get(hour_key, 0)
        if current_count >= MAX_MESSAGES_PER_AGENT:
            return False, "Agent {} exceeded hourly limit".format(agent)
        active_threads = sum(
            1 for t in self.threads.values()
            if t.phase not in [MessagePhase.COMPLETE, MessagePhase.KILLED,
                               MessagePhase.TIMED_OUT, MessagePhase.ERROR]
        )
        if active_threads >= MAX_CONCURRENT_THREADS:
            return False, "Max concurrent threads reached"
        return True, "OK"

    def create_thread(self, sender, recipient, content, thread_type="request"):
        if self._check_kill_switch():
            return {"success": False, "error": "Kill switch activated"}
        can_send, reason = self._check_rate_limit(sender)
        if not can_send:
            return {"success": False, "error": reason}
        thread_id = "thread_{}_{}_{}".format(int(time.time()), sender, recipient)
        thread = MessageThread(thread_id, thread_type)
        thread.participants = [sender, recipient]
        thread.current_agent = sender
        thread.next_agent = recipient
        result = thread.add_message(sender, content)
        if not result["success"]:
            return result
        thread.phase = MessagePhase.WAITING_FOR_REPLY
        self.threads[thread_id] = thread
        self._save_thread(thread)
        hour_key = int(time.time() // 3600)
        if sender not in self.agent_message_counts:
            self.agent_message_counts[sender] = {}
        self.agent_message_counts[sender][hour_key] = self.agent_message_counts[sender].get(hour_key, 0) + 1
        self.last_message_times[sender] = time.time()
        return {"success": True, "thread": thread.get_status()}

    def add_response(self, thread_id, agent, content):
        if self._check_kill_switch():
            return {"success": False, "error": "Kill switch activated"}
        if thread_id not in self.threads:
            return {"success": False, "error": "Thread not found"}
        thread = self.threads[thread_id]
        if thread.killed:
            return {"success": False, "error": "Thread is killed"}
        if thread.phase in [MessagePhase.COMPLETE, MessagePhase.TIMED_OUT]:
            return {"success": False, "error": "Thread is closed"}
        can_send, reason = self._check_rate_limit(agent)
        if not can_send:
            return {"success": False, "error": reason}
        if thread.next_agent and thread.next_agent != agent:
            return {"success": False, "error": "Waiting for {}".format(thread.next_agent)}
        result = thread.add_message(agent, content)
        if not result["success"]:
            return result
        thread.phase = MessagePhase.RESPONSE_READY
        thread.current_agent, thread.next_agent = thread.next_agent, thread.current_agent
        self._save_thread(thread)
        hour_key = int(time.time() // 3600)
        if agent not in self.agent_message_counts:
            self.agent_message_counts[agent] = {}
        self.agent_message_counts[agent][hour_key] = self.agent_message_counts[agent].get(hour_key, 0) + 1
        self.last_message_times[agent] = time.time()
        return {"success": True, "thread": thread.get_status()}

    def kill_thread(self, thread_id, reason="Manual kill"):
        if thread_id not in self.threads:
            return {"success": False, "error": "Thread not found"}
        thread = self.threads[thread_id]
        result = thread.kill(reason)
        if result["success"]:
            self._save_thread(thread)
        return result

    def get_thread(self, thread_id):
        if thread_id not in self.threads:
            return {"success": False, "error": "Thread not found"}
        return {"success": True, "thread": self.threads[thread_id].get_status()}

    def list_threads(self, status=None):
        threads = []
        for thread in self.threads.values():
            if status is None or thread.phase.value == status:
                threads.append(thread.get_status())
        return {"success": True, "threads": threads, "count": len(threads)}

    def check_timeouts(self):
        timed_out = []
        for thread in self.threads.values():
            if thread.killed or thread.phase in [MessagePhase.COMPLETE, MessagePhase.TIMED_OUT]:
                continue
            created = datetime.datetime.fromisoformat(thread.created_at)
            elapsed = (datetime.datetime.utcnow() - created).total_seconds() / 60
            if elapsed > thread.timeout:
                thread.timeout()
                timed_out.append(thread.thread_id)
                self._save_thread(thread)
        return timed_out

    def _save_thread(self, thread):
        filepath = os.path.join(THREADS_DIR, "{}.json".format(thread.thread_id))
        with open(filepath, "w") as f:
            json.dump(thread.to_dict(), f, indent=2)

    def _load_threads(self):
        if not os.path.exists(THREADS_DIR):
            return
        for filename in os.listdir(THREADS_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(THREADS_DIR, filename)
                with open(filepath, "r") as f:
                    data = json.load(f)
                    thread = MessageThread.from_dict(data)
                    self.threads[thread.thread_id] = thread
