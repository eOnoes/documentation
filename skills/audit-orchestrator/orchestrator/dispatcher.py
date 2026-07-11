"""
Audit Orchestrator — Agent Dispatcher

Fires agents via one-shot Hermes cron jobs (for Cyony/Echo) or file drops
(for Tripp). Each cron creates a fresh agent session with a self-contained
prompt, pinned model, and constrained toolsets.
"""

import os
import json
import datetime

from .config import (
    PROJECTS_DIR,
    PHASE_OWNERS,
    AGENT_MODELS,
    PHASE_PLAN_FILES,
    PHASE_OUTPUT_FILES,
    PHASE_STATUS_FILES,
)
from .models import AuditProject


# ── Constants ─────────────────────────────────────────────────────────

ENABLED_TOOLSETS = ["file", "terminal", "search"]

TRIGGER_DIR = ".triggers"


# ── Internal Helpers ──────────────────────────────────────────────────

def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string with Z suffix."""
    return datetime.datetime.utcnow().isoformat() + "Z"


# ── Public API ────────────────────────────────────────────────────────

def trigger_hermes_agent(
    agent_name: str,
    project_id: str,
    phase: str,
    project_path: str,
    model_override: dict | None = None,
    prompt: str | None = None,
) -> dict:
    """
    Create a one-shot Hermes cron job for an agent.

    Parameters match the spec signature; ``prompt`` is accepted as an
    optional override so that ``dispatch_agent`` can supply a fully-
    rendered prompt from ``build_agent_prompt()``.

    Returns the cron-job dict (the job_id would come from the Hermes API
    in production — for v1 the dict itself is the return value).
    """
    # Determine model: override > per-agent default > MiMo fallback
    model_config = (
        model_override
        or AGENT_MODELS.get(agent_name, {"provider": "xiaomi", "model": "mimo-v2.5"})
    )

    job_name = f"{agent_name}-audit-{project_id}-{phase}"

    job: dict = {
        "name": job_name,
        "schedule": _now_iso(),
        "prompt": prompt or _build_basic_prompt(agent_name, project_id, phase, project_path),
        "enabled_toolsets": ENABLED_TOOLSETS,
        "model": model_config,
        "deliver": "local",
    }

    # In production this would POST to the Hermes cron API.
    # The return value is the full job dict so callers can inspect it.
    return job


def trigger_tripp(project_dir: str, phase: str) -> str:
    """
    Drop a trigger JSON file for Tripp (OpenClaw) to pick up.

    Creates ``{project_dir}/.triggers/`` if it doesn't exist and writes::

        {"trigger": true, "agent": "tripp", "phase": "...", "dispatched_at": "ISO"}

    Returns the path of the trigger file.
    """
    triggers_dir = os.path.join(project_dir, TRIGGER_DIR)
    os.makedirs(triggers_dir, exist_ok=True)

    trigger_path = os.path.join(triggers_dir, f"{phase}.json")

    trigger_data: dict = {
        "trigger": True,
        "agent": "tripp",
        "phase": phase,
        "dispatched_at": _now_iso(),
    }

    with open(trigger_path, "w") as fh:
        json.dump(trigger_data, fh, indent=2)

    return trigger_path


def check_cron_status(job_id: str) -> str:
    """
    Check whether a one-shot Hermes cron job has completed.

    Returns one of: ``"completed"``, ``"failed"``, ``"timeout"``, ``"running"``.

    v1 stub — always returns ``"completed"``.  Real implementation will
    call the Hermes API once that integration is ready.
    """
    return "completed"


def dispatch_agent(project: AuditProject) -> dict:
    """
    High-level dispatch: determine the agent for the current phase and
    fire the appropriate trigger (Hermes cron or Tripp file-drop).

    Returns a dispatch info dict with keys:
        agent, phase, method, project_id, …
    """
    agent = project.get_next_agent()
    phase = project.phase
    project_path = os.path.join(PROJECTS_DIR, project.project_id)

    # Build prompt only for agents that have dispatch mappings
    try:
        prompt = build_agent_prompt(project)
    except ValueError:
        prompt = None

    if agent == "tripp":
        trigger_file = trigger_tripp(project_path, phase)
        return {
            "agent": agent,
            "phase": phase,
            "method": "file_drop",
            "trigger_file": trigger_file,
            "project_id": project.project_id,
        }
    elif agent in ("echo", "cyony"):
        kwargs = dict(
            agent_name=agent,
            project_id=project.project_id,
            phase=phase,
            project_path=project_path,
        )
        if prompt is not None:
            kwargs["prompt"] = prompt
        job = trigger_hermes_agent(**kwargs)
        return {
            "agent": agent,
            "phase": phase,
            "method": "hermes_cron",
            "job": job,
            "project_id": project.project_id,
        }
    else:
        return {
            "agent": agent,
            "phase": phase,
            "method": "none",
            "project_id": project.project_id,
            "error": f"No dispatch method for agent: {agent}",
        }


def build_agent_prompt(project: AuditProject) -> str:
    """
    Create the full, self-contained dispatch prompt for the project's
    current phase.  Wrapper around ``AuditProject.get_dispatch_prompt()``.
    """
    return project.get_dispatch_prompt()


# ── Internal Helpers (continued) ──────────────────────────────────────

def _build_basic_prompt(
    agent_name: str, project_id: str, phase: str, project_path: str
) -> str:
    """
    Build a minimal prompt when no full AuditProject is available.
    Used as fallback inside ``trigger_hermes_agent`` when ``prompt=None``.
    """
    plan_file = PHASE_PLAN_FILES.get(phase, "LEAD_PLAN.md")
    output_file = PHASE_OUTPUT_FILES.get(phase, f"{agent_name.upper()}_AUDIT.md")
    status_file = PHASE_STATUS_FILES.get(phase, f".status/{agent_name}_unknown.json")

    plan_path = os.path.join(project_path, plan_file)
    output_path = os.path.join(project_path, output_file)
    status_path = os.path.join(project_path, status_file)

    if "CONSOLIDATE" in phase:
        intro = f"You are {agent_name}. You are consolidating audit findings into a plan update."
    else:
        intro = f"You are {agent_name}. You are auditing a project plan."

    return f"""{intro}

PROJECT: {project_id}
YOUR PHASE: {phase}
PLAN TO AUDIT: {plan_path}

INSTRUCTIONS:
1. Read the plan file above carefully
2. Score the plan X/10
3. Write your audit to: {output_path}
4. Start your file with: <!-- AUDIT_META: agent={agent_name} | phase={phase} | started=NOW | score=X/10 -->
5. When done, use the write_file tool to create {status_path} with this exact JSON:
   {{"status":"done","agent":"{agent_name}","score":N,"summary":"brief summary"}}

CONSTRAINTS:
- Your working directory is {project_path}. Only read files within this directory.
- Do NOT use delegate_task. Do NOT spawn subagents. You are the only agent.
- Do NOT read files outside the project directory.
- Do NOT modify any files except your output and status files."""
