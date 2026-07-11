"""
Audit Orchestrator — State Machine Core

Defines AuditPhase enum, AuditProject state class, and file-system helpers
(atomic_write, file_lock). This is the foundation everything else builds on.
"""

import os
import json
import fcntl
import contextlib
import datetime
from enum import Enum

from .config import (
    PROJECTS_DIR,
    PHASE_OWNERS,
    PHASE_ARTIFACTS,
    PHASE_TIMEOUTS,
    PHASE_PLAN_FILES,
    PHASE_OUTPUT_FILES,
    PHASE_STATUS_FILES,
    AGENT_MODELS,
)


# ── Phase Enum ─────────────────────────────────────────────────────────

class AuditPhase(Enum):
    PLANNING          = "PLANNING"
    READY_FOR_AUDIT   = "READY_FOR_AUDIT"
    R1_ECHO           = "R1_ECHO"
    R1_TRIPP          = "R1_TRIPP"
    R1_CONSOLIDATE    = "R1_CONSOLIDATE"
    R2_ECHO           = "R2_ECHO"
    R2_TRIPP          = "R2_TRIPP"
    R2_CONSOLIDATE    = "R2_CONSOLIDATE"
    READY_FOR_BUILD   = "READY_FOR_BUILD"
    BUILDING          = "BUILDING"
    STORED            = "STORED"
    TRASHED           = "TRASHED"
    CANCELLED         = "CANCELLED"


# ── Valid Sequential Transition Order ──────────────────────────────────
# advance() moves one step forward through this list.
# TRASHED, CANCELLED, STORED are terminal / reached via special methods only.

PHASE_ORDER = [
    AuditPhase.PLANNING,
    AuditPhase.READY_FOR_AUDIT,
    AuditPhase.R1_ECHO,
    AuditPhase.R1_TRIPP,
    AuditPhase.R1_CONSOLIDATE,
    AuditPhase.R2_ECHO,
    AuditPhase.R2_TRIPP,
    AuditPhase.R2_CONSOLIDATE,
    AuditPhase.READY_FOR_BUILD,
    AuditPhase.BUILDING,
]


# ── AuditProject ───────────────────────────────────────────────────────

class AuditProject:
    """Full v3 state object for a single audit project."""

    def __init__(
        self,
        project_id: str,
        name: str,
        lead: str = "Cyony",
        phase: str = "PLANNING",
        round: int = 1,
        created_at: str | None = None,
        updated_at: str | None = None,
        phase_started_at: str | None = None,
        timeout_minutes: int | None = None,
        model: dict | None = None,
        trashed_at: str | None = None,
        cancelled_at: str | None = None,
        cancel_reason: str | None = None,
        error_tracking: dict | None = None,
        artifacts: dict | None = None,
    ):
        self.project_id = project_id
        self.name = name
        self.lead = lead
        self.phase = phase
        self.round = round

        now = _now_iso()
        self.created_at = created_at or now
        self.updated_at = updated_at or now
        self.phase_started_at = phase_started_at or now

        self.timeout_minutes = timeout_minutes
        self.model = model or dict(AGENT_MODELS.get(PHASE_OWNERS.get(phase, "cyony"),
                                                     {"provider": "xiaomi", "model": "mimo-v2.5"}))

        self.trashed_at = trashed_at
        self.cancelled_at = cancelled_at
        self.cancel_reason = cancel_reason

        self.error_tracking = error_tracking or {
            "consecutive_errors": 0,
            "last_error_at": None,
            "alert_suppressed": False,
        }

        self.artifacts = artifacts or {
            "plan": "LEAD_PLAN.md",
            "echo_r1": None,
            "tripp_r1": None,
            "lead_v2": None,
            "echo_r2": None,
            "tripp_r2": None,
            "final": None,
        }

    # ── Phase Transitions ──────────────────────────────────────────────

    def advance(self):
        """Move to the next phase in PHASE_ORDER. Raises if already terminal."""
        current = AuditPhase(self.phase)
        idx = PHASE_ORDER.index(current)
        if idx >= len(PHASE_ORDER) - 1:
            raise ValueError(
                f"Cannot advance from terminal phase {self.phase}"
            )
        next_phase = PHASE_ORDER[idx + 1]
        self.phase = next_phase.value

        # Update round when crossing R1 → R2 boundary
        if next_phase in (AuditPhase.R2_ECHO, AuditPhase.R2_TRIPP,
                          AuditPhase.R2_CONSOLIDATE, AuditPhase.READY_FOR_BUILD,
                          AuditPhase.BUILDING):
            self.round = 2

        # Update timeout from phase config
        timeout = PHASE_TIMEOUTS.get(next_phase.value)
        if timeout is not None:
            self.timeout_minutes = timeout

        now = _now_iso()
        self.phase_started_at = now
        self.updated_at = now

        # Reset error tracking on successful phase advance
        self.error_tracking["consecutive_errors"] = 0
        self.error_tracking["alert_suppressed"] = False

    def get_next_agent(self) -> str:
        """Return the agent name responsible for the current phase."""
        return PHASE_OWNERS.get(self.phase, "unknown")

    def get_dispatch_prompt(self, project_path: str | None = None) -> str:
        """
        Build a complete, self-contained prompt string for the current phase.
        All variables are filled in. Includes scope boundary and no-subagents rules.
        """
        agent = self.get_next_agent()
        phase = self.phase

        if project_path is None:
            project_path = os.path.join(PROJECTS_DIR, self.project_id)

        plan_file = PHASE_PLAN_FILES.get(phase)
        output_file = PHASE_OUTPUT_FILES.get(phase)
        status_file = PHASE_STATUS_FILES.get(phase)

        if not plan_file or not output_file or not status_file:
            raise ValueError(
                f"Phase {phase} is not an agent-dispatch phase "
                f"(no plan/output/status mapping)"
            )

        plan_path = os.path.join(project_path, plan_file)
        output_path = os.path.join(project_path, output_file)
        status_path = os.path.join(project_path, status_file)

        # Build conditional reference block
        conditional_ref = _build_conditional_reference(phase, project_path)

        # Intro line adapts for audit vs consolidation
        if "CONSOLIDATE" in phase:
            intro = (
                f"You are {agent}. You are consolidating audit findings "
                f"into a plan update."
            )
        else:
            intro = f"You are {agent}. You are auditing a project plan."

        prompt = f"""{intro}

PROJECT: {self.name}
YOUR PHASE: {phase} (Round {self.round})
PLAN TO AUDIT: {plan_path}

{conditional_ref}

INSTRUCTIONS:
1. Read the plan file above carefully
2. Score the plan X/10
3. Write your audit to: {output_path}
4. Start your file with: <!-- AUDIT_META: agent={agent} | phase={phase} | started=NOW | score=X/10 -->
5. When done, use the write_file tool to create {status_path} with this exact JSON:
   {{"status":"done","agent":"{agent}","score":N,"summary":"brief summary"}}

CONSTRAINTS:
- Your working directory is {project_path}. Only read files within this directory.
- Do NOT use delegate_task. Do NOT spawn subagents. You are the only agent.
- Do NOT read files outside the project directory.
- Do NOT modify any files except your output and status files."""

        return prompt

    def trash(self):
        """Mark project as TRASHED with timestamp."""
        self.phase = AuditPhase.TRASHED.value
        self.trashed_at = _now_iso()
        self.updated_at = _now_iso()

    def cancel(self, reason: str):
        """Mark project as CANCELLED with timestamp and reason."""
        self.phase = AuditPhase.CANCELLED.value
        self.cancelled_at = _now_iso()
        self.cancel_reason = reason
        self.updated_at = _now_iso()

    def restore(self):
        """
        Restore a TRASHED or CANCELLED project.
        Clears trashed_at / cancelled_at.
        Sets phase to READY_FOR_BUILD if audit artifacts exist, else PLANNING.
        """
        self.trashed_at = None
        self.cancelled_at = None
        self.cancel_reason = None

        # If we have a final plan, restore to READY_FOR_BUILD
        if self.artifacts.get("final"):
            self.phase = AuditPhase.READY_FOR_BUILD.value
        else:
            self.phase = AuditPhase.PLANNING.value

        self.updated_at = _now_iso()

    def days_until_removal(self) -> int:
        """
        Returns days remaining before auto-delete (20 - days since trashed_at).
        Returns 0 if not trashed or already expired.
        """
        if not self.trashed_at:
            return 0
        trashed_dt = _parse_iso(self.trashed_at)
        now_dt = datetime.datetime.utcnow()
        delta = (now_dt - trashed_dt).days
        remaining = 20 - delta
        return max(remaining, 0)

    # ── Serialization ──────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize to dict matching the v3 state file format."""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "lead": self.lead,
            "phase": self.phase,
            "round": self.round,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "phase_started_at": self.phase_started_at,
            "timeout_minutes": self.timeout_minutes,
            "model": dict(self.model),
            "trashed_at": self.trashed_at,
            "cancelled_at": self.cancelled_at,
            "cancel_reason": self.cancel_reason,
            "error_tracking": dict(self.error_tracking),
            "artifacts": dict(self.artifacts),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuditProject":
        """Deserialize from a dict (e.g. parsed JSON state file)."""
        return cls(
            project_id=data["project_id"],
            name=data["name"],
            lead=data.get("lead", "Cyony"),
            phase=data.get("phase", "PLANNING"),
            round=data.get("round", 1),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            phase_started_at=data.get("phase_started_at"),
            timeout_minutes=data.get("timeout_minutes"),
            model=data.get("model"),
            trashed_at=data.get("trashed_at"),
            cancelled_at=data.get("cancelled_at"),
            cancel_reason=data.get("cancel_reason"),
            error_tracking=data.get("error_tracking"),
            artifacts=data.get("artifacts"),
        )


# ── File System Helpers ────────────────────────────────────────────────

def atomic_write(path, content: str):
    """
    Atomically write content to a file using .tmp + os.rename().
    Ensures readers never see a partially-written file.
    """
    path = str(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmp_path, path)


@contextlib.contextmanager
def file_lock(path):
    """
    Context manager for advisory file locking using fcntl.flock(LOCK_EX).
    Creates a .lock sidecar file next to the target.
    """
    lock_path = str(path) + ".lock"
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


# ── Internal Helpers ───────────────────────────────────────────────────

def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string with Z suffix."""
    return datetime.datetime.utcnow().isoformat() + "Z"


def _parse_iso(s: str) -> datetime.datetime:
    """Parse an ISO-8601 string (with or without Z suffix) to datetime."""
    s = s.rstrip("Z")
    # Handle both with and without fractional seconds
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse ISO timestamp: {s!r}")


def _build_conditional_reference(phase: str, project_path: str) -> str:
    """
    Build the conditional reference block for the dispatch prompt.
    R1 auditors are independent (no references).
    R2 auditors reference R1 audits and each other's work.
    Consolidation reads the relevant round's audits.
    """
    lines = []

    if phase == "R1_ECHO" or phase == "R1_TRIPP":
        # R1 auditors are independent — no cross-references
        return ""

    if phase == "R1_CONSOLIDATE":
        lines.append("Also read the Round 1 audits:")
        lines.append(f"- {os.path.join(project_path, 'ECHO_AUDIT_R1.md')}")
        lines.append(f"- {os.path.join(project_path, 'TRIPP_AUDIT_R1.md')}")

    elif phase == "R2_ECHO":
        lines.append("Also read the Round 1 audits for context:")
        lines.append(f"- {os.path.join(project_path, 'ECHO_AUDIT_R1.md')}")
        lines.append(f"- {os.path.join(project_path, 'TRIPP_AUDIT_R1.md')}")
        lines.append(f"- {os.path.join(project_path, 'ROUND_SUMMARY_R1.md')}")

    elif phase == "R2_TRIPP":
        lines.append(f"Also read Echo's R2 audit: {os.path.join(project_path, 'ECHO_AUDIT_R2.md')}")
        lines.append("Also read Round 1 audits for context:")
        lines.append(f"- {os.path.join(project_path, 'ECHO_AUDIT_R1.md')}")
        lines.append(f"- {os.path.join(project_path, 'TRIPP_AUDIT_R1.md')}")
        lines.append(f"- {os.path.join(project_path, 'ROUND_SUMMARY_R1.md')}")

    elif phase == "R2_CONSOLIDATE":
        lines.append("Also read the Round 2 audits:")
        lines.append(f"- {os.path.join(project_path, 'ECHO_AUDIT_R2.md')}")
        lines.append(f"- {os.path.join(project_path, 'TRIPP_AUDIT_R2.md')}")

    return "\n".join(lines)
