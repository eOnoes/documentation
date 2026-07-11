"""
Audit Orchestrator — Action Handlers (Phase 6)

Actions Eddie can perform on projects at various phases:
- Approve build (yes)
- Store
- Trash
- Cancel
- Restore
- Extend timeout
- Cleanup expired trash
"""

import os
import json
import shutil
import datetime

from .config import PROJECTS_DIR
from .models import AuditPhase, atomic_write
from .notifier import format_notification


# ── Internal Helpers ───────────────────────────────────────────────────


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string with Z suffix."""
    return datetime.datetime.utcnow().isoformat() + "Z"


def _get_project_dir(project_id: str) -> str:
    """Return the filesystem path for a project directory."""
    return os.path.join(PROJECTS_DIR, project_id)


def _save_project_state(project) -> None:
    """Atomic write of project state to project_state.json."""
    project_dir = _get_project_dir(project.project_id)
    os.makedirs(project_dir, exist_ok=True)
    state_path = os.path.join(project_dir, "project_state.json")
    content = json.dumps(project.to_dict(), indent=2)
    atomic_write(state_path, content)


# ── Action Functions ───────────────────────────────────────────────────


def action_yes(project, orchestrator):
    """
    Eddie approves build — set phase to BUILDING.

    Args:
        project: AuditProject instance
        orchestrator: AuditOrchestrator instance (used for save_project)

    Returns:
        True on success.
    """
    project.phase = AuditPhase.BUILDING.value
    project.updated_at = _now_iso()

    msg = format_notification("✅", f"Build started for {project.name}", "")
    print(msg)

    orchestrator.save_project(project.project_id)
    return True


def action_store(project):
    """
    Eddie parks the project — set phase to STORED.

    Args:
        project: AuditProject instance

    Returns:
        True on success.
    """
    project.phase = AuditPhase.STORED.value
    project.updated_at = _now_iso()

    msg = format_notification(
        "📁", f"{project.name} stored. Restore anytime.", ""
    )
    print(msg)

    _save_project_state(project)
    return True


def action_trash(project):
    """
    Eddie trashes the project — set phase to TRASHED with timestamp.

    Args:
        project: AuditProject instance

    Returns:
        True on success.
    """
    project.trash()

    msg = format_notification(
        "🗑️",
        f"{project.name} trashed. Auto-deleted in 20 days.",
        "",
        actions=["Rescue"],
    )
    print(msg)

    _save_project_state(project)
    return True


def action_cancel(project, reason):
    """
    Eddie kills the project mid-audit.

    Args:
        project: AuditProject instance
        reason: Non-empty cancellation reason string.

    Returns:
        True on success.

    Raises:
        ValueError: If reason is empty or whitespace-only.
    """
    if not reason or not reason.strip():
        raise ValueError("Cancellation reason must be non-empty")

    project.cancel(reason)

    # Move project directory to .cancelled/ suffix
    project_dir = _get_project_dir(project.project_id)
    cancelled_dir = project_dir + ".cancelled"
    if os.path.exists(project_dir):
        shutil.move(project_dir, cancelled_dir)
    else:
        # Create the .cancelled dir even if original didn't exist
        os.makedirs(cancelled_dir, exist_ok=True)

    # Create metadata file
    metadata = {
        "cancelled_at": project.cancelled_at,
        "reason": project.cancel_reason,
        "project_id": project.project_id,
        "name": project.name,
    }
    metadata_path = os.path.join(cancelled_dir, "cancelled.json")
    os.makedirs(cancelled_dir, exist_ok=True)
    atomic_write(metadata_path, json.dumps(metadata, indent=2))

    # Save project state inside the cancelled dir
    state_path = os.path.join(cancelled_dir, "project_state.json")
    content = json.dumps(project.to_dict(), indent=2)
    atomic_write(state_path, content)

    msg = format_notification(
        "❌",
        f"{project.name} cancelled.",
        f"Reason: {project.cancel_reason}",
    )
    print(msg)

    return True


def action_restore(project):
    """
    Restore a project from STORED, TRASHED, or CANCELLED.

    Args:
        project: AuditProject instance

    Returns:
        True on success.

    Raises:
        ValueError: If project is not in a restorable phase.
    """
    restorable_phases = {
        AuditPhase.STORED.value,
        AuditPhase.TRASHED.value,
        AuditPhase.CANCELLED.value,
    }
    if project.phase not in restorable_phases:
        raise ValueError(
            f"Cannot restore project in phase {project.phase}. "
            f"Must be in one of: {', '.join(sorted(restorable_phases))}"
        )

    # If CANCELLED, move directory back from .cancelled/ suffix
    if project.phase == AuditPhase.CANCELLED.value:
        cancelled_dir = _get_project_dir(project.project_id) + ".cancelled"
        original_dir = _get_project_dir(project.project_id)
        if os.path.exists(cancelled_dir) and not os.path.exists(original_dir):
            shutil.move(cancelled_dir, original_dir)
        elif os.path.exists(cancelled_dir) and os.path.exists(original_dir):
            # Both exist — move cancelled to original (overwrite)
            shutil.move(cancelled_dir, original_dir)

    # Restore project state (clears timestamps, sets phase based on artifacts)
    project.restore()

    msg = format_notification(
        "🔄",
        f"{project.name} restored to {project.phase}",
        "",
    )
    print(msg)

    _save_project_state(project)
    return True


def action_extend_timeout(project, minutes=30):
    """
    Extend the current phase timeout.

    Args:
        project: AuditProject instance
        minutes: Additional minutes to add (default: 30)

    Returns:
        True on success.
    """
    if project.timeout_minutes is None:
        project.timeout_minutes = minutes
    else:
        project.timeout_minutes += minutes

    # Reset the clock — update phase_started_at to now
    project.phase_started_at = _now_iso()
    project.updated_at = _now_iso()

    msg = format_notification(
        "⏰",
        f"Timeout extended +{minutes}min for {project.name}",
        "",
    )
    print(msg)

    _save_project_state(project)
    return True


def cleanup_expired_trash(projects_dict):
    """
    Delete projects that have been trashed for more than 20 days.

    Args:
        projects_dict: dict mapping project_id -> AuditProject.
            Modified in place (expired entries removed).

    Returns:
        List of deleted project IDs.
    """
    deleted_ids = []

    for project_id, project in list(projects_dict.items()):
        if project.phase != AuditPhase.TRASHED.value:
            continue

        if project.days_until_removal() <= 0:
            # Delete project directory
            project_dir = _get_project_dir(project_id)
            if os.path.exists(project_dir):
                shutil.rmtree(project_dir)

            # Remove from dict
            del projects_dict[project_id]
            deleted_ids.append(project_id)

    return deleted_ids
