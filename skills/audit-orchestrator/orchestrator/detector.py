"""
Audit Orchestrator — Completion Detection + Error Handling

Checks if an agent has completed its work by looking for JSON status files.
Handles artifact validation, error tracking, and score validation.
"""

import os
import json
import time
import datetime

from .config import (
    PHASE_OUTPUT_FILES,
    PHASE_STATUS_FILES,
    MAX_ALERTSUPPRESSION,
)
from .models import AuditProject


# ── Completion Detection ───────────────────────────────────────────────

def check_completion(project_dir: str, phase: str) -> bool:
    """
    Check if an agent has completed its work.

    Looks for the status file at {project_dir}/.status/{phase}.json.
    Waits 5 seconds (settling time) before reading the artifact.
    Returns True if file exists AND is valid JSON.
    """
    status_file = PHASE_STATUS_FILES.get(phase)
    if status_file is None:
        return False

    status_path = os.path.join(project_dir, status_file)

    # Settling time — wait before reading
    time.sleep(5)

    if not os.path.exists(status_path):
        return False

    try:
        with open(status_path, "r") as f:
            json.load(f)
        return True
    except (json.JSONDecodeError, OSError):
        return False


# ── Artifact Validation ───────────────────────────────────────────────

def validate_artifact(project_dir: str, phase: str) -> tuple[bool, str | None]:
    """
    Read the output artifact file for a given phase.

    Checks:
      (a) file exists
      (b) content > 100 chars

    Uses PHASE_OUTPUT_FILES from config to find the artifact.

    Returns (is_valid, error_string). error_string is None on success.
    """
    output_file = PHASE_OUTPUT_FILES.get(phase)
    if output_file is None:
        return False, f"No output file configured for phase {phase}"

    artifact_path = os.path.join(project_dir, output_file)

    if not os.path.exists(artifact_path):
        return False, f"Artifact file does not exist: {artifact_path}"

    try:
        with open(artifact_path, "r") as f:
            content = f.read()
    except OSError as e:
        return False, f"Failed to read artifact: {e}"

    if len(content) == 0:
        return False, f"Artifact file is empty: {artifact_path}"

    if len(content) <= 100:
        return False, f"Artifact too short ({len(content)} chars, need >100): {artifact_path}"

    return True, None


# ── Status File Parsing ───────────────────────────────────────────────

def parse_status(project_dir: str, phase: str) -> dict:
    """
    Read and parse the JSON status file for a given phase.

    Returns the parsed dict.
    Raises ValueError or FileNotFoundError on missing/malformed files.
    """
    status_file = PHASE_STATUS_FILES.get(phase)
    if status_file is None:
        raise ValueError(f"No status file configured for phase {phase}")

    status_path = os.path.join(project_dir, status_file)

    if not os.path.exists(status_path):
        raise FileNotFoundError(f"Status file not found: {status_path}")

    with open(status_path, "r") as f:
        raw = f.read()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON in {status_path}: {e}") from e


def validate_status_json(raw_content: str) -> tuple[dict | None, str | None]:
    """
    Validate raw JSON content from a status file.

    Returns (parsed_dict, error_string).
    error_string is None on success.
    """
    try:
        parsed = json.loads(raw_content)
        return parsed, None
    except json.JSONDecodeError as e:
        return None, f"Malformed JSON: {e}"


# ── Error Tracking ─────────────────────────────────────────────────────

def record_error(project: AuditProject) -> bool:
    """
    Record an error for the project.

    Increments consecutive_errors, sets last_error_at, sets alert_suppressed=True
    if consecutive_errors >= MAX_ALERTSUPPRESSION.

    Returns True if alert should be suppressed, False otherwise.
    """
    project.error_tracking["consecutive_errors"] += 1
    project.error_tracking["last_error_at"] = datetime.datetime.utcnow().isoformat() + "Z"

    if project.error_tracking["consecutive_errors"] >= MAX_ALERTSUPPRESSION:
        project.error_tracking["alert_suppressed"] = True
        return True

    return False


def reset_errors(project: AuditProject) -> None:
    """
    Reset error tracking on successful phase advance.

    Sets consecutive_errors to 0, alert_suppressed to False.
    """
    project.error_tracking["consecutive_errors"] = 0
    project.error_tracking["alert_suppressed"] = False


# ── Score Validation ───────────────────────────────────────────────────

def check_scores(project_dir: str) -> tuple[str | None, dict]:
    """
    Read both R1 audit status files, extract scores.

    If BOTH scores < 5 → returns ("both_low", scores).
    If scores differ by > 4 → returns ("wide_gap", scores).
    Otherwise returns (None, scores).

    scores is a dict like {"echo_r1": 7, "tripp_r1": 8}.
    """
    scores = {}

    # Read Echo R1 status
    echo_path = os.path.join(project_dir, PHASE_STATUS_FILES.get("R1_ECHO", ""))
    if os.path.exists(echo_path):
        with open(echo_path, "r") as f:
            try:
                data = json.load(f)
                scores["echo_r1"] = data.get("score")
            except (json.JSONDecodeError, OSError):
                pass

    # Read Tripp R1 status
    tripp_path = os.path.join(project_dir, PHASE_STATUS_FILES.get("R1_TRIPP", ""))
    if os.path.exists(tripp_path):
        with open(tripp_path, "r") as f:
            try:
                data = json.load(f)
                scores["tripp_r1"] = data.get("score")
            except (json.JSONDecodeError, OSError):
                pass

    # Validate scores
    echo_score = scores.get("echo_r1")
    tripp_score = scores.get("tripp_r1")

    # Both scores must be present for validation
    if echo_score is not None and tripp_score is not None:
        if echo_score < 5 and tripp_score < 5:
            return "both_low", scores

        if abs(echo_score - tripp_score) > 4:
            return "wide_gap", scores

    return None, scores
