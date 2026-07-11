"""
Audit Orchestrator — Configuration Constants

All paths, timeouts, agent configs, and phase mappings.
"""

import os

# ── Paths ──────────────────────────────────────────────────────────────
PROJECTS_DIR = "/opt/data/shared/audit-workflow"
SHARED_DIR = "/opt/data/shared"
TRIPP_PICKUP = "/opt/data/shared/tripp-dispatch"

# ── Timeouts ───────────────────────────────────────────────────────────
DEFAULT_AUDIT_TIMEOUT = 120          # minutes (per audit phase)
DEFAULT_CONSOLIDATION_TIMEOUT = 30   # minutes (per consolidation phase)
TRASH_RETENTION_DAYS = 20            # days before auto-delete
MARKER_CHECK_INTERVAL = 30           # seconds between polling cycles
IDLE_REMINDER_HOURS = 48             # hours at READY_FOR_BUILD before reminder
IDLE_AUTOSTORE_DAYS = 7              # days at READY_FOR_BUILD before auto-store
TRASH_WARNING_DAYS = 13              # days into trash before "7 days left" warning
MAX_ALERTSUPPRESSION = 3             # consecutive errors before suppressing alerts

# ── Telegram Notification ──────────────────────────────────────────────
TELEGRAM_CHAT_ID = "8808479511"      # Eddie's Telegram chat ID
TELEGRAM_BOT_TOKEN_PATH = "/opt/data/.env"  # File containing TELEGRAM_BOT_TOKEN=...
TELEGRAM_ENABLED = True              # Set False to disable live sends

# ── Agent → Model Mapping ──────────────────────────────────────────────
# Audits use MiMo 2.5; consolidation uses DeepSeek Flash.
AGENT_MODELS = {
    "echo":   {"provider": "xiaomi",   "model": "mimo-v2.5"},
    "tripp":  {"provider": "xiaomi",   "model": "mimo-v2.5"},
    "cyony":  {"provider": "deepseek", "model": "deepseek-v3"},
    "codex":  {"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
}

# ── Phase → Owner Agent ────────────────────────────────────────────────
PHASE_OWNERS = {
    "PLANNING":           "cyony",
    "READY_FOR_AUDIT":    "orchestrator",
    "R1_ECHO":            "echo",
    "R1_TRIPP":           "tripp",
    "R1_CONSOLIDATE":     "cyony",
    "R2_ECHO":            "echo",
    "R2_TRIPP":           "tripp",
    "R2_CONSOLIDATE":     "cyony",
    "READY_FOR_BUILD":    "orchestrator",
    "BUILDING":           "codex",
}

# ── Phase → Output Artifact Filenames ──────────────────────────────────
PHASE_ARTIFACTS = {
    "PLANNING":           ["LEAD_PLAN.md"],
    "READY_FOR_AUDIT":    [],
    "R1_ECHO":            ["ECHO_AUDIT_R1.md"],
    "R1_TRIPP":           ["TRIPP_AUDIT_R1.md"],
    "R1_CONSOLIDATE":     ["ROUND_SUMMARY_R1.md", "LEAD_PLAN_V2.md"],
    "R2_ECHO":            ["ECHO_AUDIT_R2.md"],
    "R2_TRIPP":           ["TRIPP_AUDIT_R2.md"],
    "R2_CONSOLIDATE":     ["ROUND_SUMMARY_R2.md", "FINAL_PLAN.md"],
    "READY_FOR_BUILD":    [],
    "BUILDING":           ["EXECUTION_LOG.md"],
}

# ── Phase → Timeout (minutes) ──────────────────────────────────────────
# None means no timeout (non-agent phases).
PHASE_TIMEOUTS = {
    "PLANNING":           None,
    "READY_FOR_AUDIT":    None,
    "R1_ECHO":            DEFAULT_AUDIT_TIMEOUT,
    "R1_TRIPP":           DEFAULT_AUDIT_TIMEOUT,
    "R1_CONSOLIDATE":     DEFAULT_CONSOLIDATION_TIMEOUT,
    "R2_ECHO":            DEFAULT_AUDIT_TIMEOUT,
    "R2_TRIPP":           DEFAULT_AUDIT_TIMEOUT,
    "R2_CONSOLIDATE":     DEFAULT_CONSOLIDATION_TIMEOUT,
    "READY_FOR_BUILD":    None,
    "BUILDING":           None,
}

# ── Phase → Plan File to Audit ─────────────────────────────────────────
PHASE_PLAN_FILES = {
    "R1_ECHO":            "LEAD_PLAN.md",
    "R1_TRIPP":           "LEAD_PLAN.md",
    "R1_CONSOLIDATE":     "LEAD_PLAN.md",
    "R2_ECHO":            "LEAD_PLAN_V2.md",
    "R2_TRIPP":           "LEAD_PLAN_V2.md",
    "R2_CONSOLIDATE":     "LEAD_PLAN_V2.md",
}

# ── Phase → Primary Output File ────────────────────────────────────────
PHASE_OUTPUT_FILES = {
    "R1_ECHO":            "ECHO_AUDIT_R1.md",
    "R1_TRIPP":           "TRIPP_AUDIT_R1.md",
    "R1_CONSOLIDATE":     "LEAD_PLAN_V2.md",
    "R2_ECHO":            "ECHO_AUDIT_R2.md",
    "R2_TRIPP":           "TRIPP_AUDIT_R2.md",
    "R2_CONSOLIDATE":     "FINAL_PLAN.md",
}

# ── Phase → Status File (relative to project dir) ──────────────────────
PHASE_STATUS_FILES = {
    "R1_ECHO":            ".status/echo_r1.json",
    "R1_TRIPP":           ".status/tripp_r1.json",
    "R1_CONSOLIDATE":     ".status/lead_r1_consolidated.json",
    "R2_ECHO":            ".status/echo_r2.json",
    "R2_TRIPP":           ".status/tripp_r2.json",
    "R2_CONSOLIDATE":     ".status/lead_final.json",
}
