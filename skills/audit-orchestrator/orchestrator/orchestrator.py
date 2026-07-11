"""
Audit Orchestrator — Main Loop (Phase 5)

30-second polling loop that checks for completion markers and advances phases.
Single-threaded by design. Pure Python — no LLM, zero token cost.
"""

import os
import json
import time
import logging
import datetime

from .config import (
    PROJECTS_DIR,
    MARKER_CHECK_INTERVAL,
    PHASE_OWNERS,
    PHASE_STATUS_FILES,
    PHASE_TIMEOUTS,
    TRASH_RETENTION_DAYS,
    IDLE_REMINDER_HOURS,
    IDLE_AUTOSTORE_DAYS,
    TRASH_WARNING_DAYS,
    MAX_ALERTSUPPRESSION,
)
from .models import AuditProject, AuditPhase, PHASE_ORDER, atomic_write
from .detector import (
    check_completion,
    validate_artifact,
    parse_status,
    record_error,
    reset_errors,
    check_scores,
)
from .dispatcher import dispatch_agent
from .notifier import (
    RateLimiter,
    notify_phase_complete,
    notify_timeout,
    notify_ready_for_build,
    notify_idle_reminder,
    notify_idle_autostore,
    notify_error,
    notify_trash_warning,
)

logger = logging.getLogger(__name__)


class AuditOrchestrator:
    """
    The heartbeat of the audit system.

    Runs a 30-second polling loop that:
    - Writes a heartbeat timestamp
    - Checks for agent completion markers
    - Validates artifacts and advances phases
    - Dispatches the next agent
    - Handles timeouts, idle detection, and trash timers
    - Notifies Eddie at key milestones
    """

    def __init__(self):
        self.projects: dict[str, AuditProject] = {}
        self.rate_limiter = RateLimiter()

        if not os.path.exists(PROJECTS_DIR):
            os.makedirs(PROJECTS_DIR, exist_ok=True)
            logger.info("Created PROJECTS_DIR: %s", PROJECTS_DIR)

    # ── Project Management ─────────────────────────────────────────────

    def load_projects(self) -> None:
        """Scan PROJECTS_DIR for subdirectories with project_state.json."""
        if not os.path.exists(PROJECTS_DIR):
            return

        for entry in os.scandir(PROJECTS_DIR):
            if not entry.is_dir():
                continue

            state_path = os.path.join(entry.path, "project_state.json")
            if not os.path.exists(state_path):
                continue

            try:
                with open(state_path, "r") as f:
                    data = json.load(f)
                project = AuditProject.from_dict(data)
                self.projects[project.project_id] = project
                logger.info("Loaded project: %s (phase=%s)", project.project_id, project.phase)
            except (json.JSONDecodeError, OSError, KeyError) as e:
                logger.warning("Failed to load project from %s: %s", state_path, e)

    def create_project(self, project_id: str, name: str, lead: str = "Cyony") -> AuditProject:
        """Create a new audit project and save state to disk."""
        project = AuditProject(project_id=project_id, name=name, lead=lead)

        # Create project directory
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        os.makedirs(project_dir, exist_ok=True)

        self.projects[project_id] = project
        self.save_project(project_id)

        # Create initial plan file placeholder
        plan_path = os.path.join(project_dir, "LEAD_PLAN.md")
        if not os.path.exists(plan_path):
            atomic_write(plan_path, f"# {name}\n\nPlan pending.\n")

        logger.info("Created project: %s", project_id)
        return project

    def start_team_audit(self, project_id: str) -> None:
        """Advance project to R1_ECHO and dispatch the first agent."""
        project = self.projects[project_id]

        # PLANNING → READY_FOR_AUDIT → R1_ECHO
        project.advance()
        project.advance()

        self.save_project(project_id)
        self.dispatch_current_agent(project_id)

        logger.info("Started team audit for %s — now at %s", project_id, project.phase)

    def save_project(self, project_id: str) -> None:
        """Atomic write of project state to project_state.json."""
        project = self.projects[project_id]
        project_dir = os.path.join(PROJECTS_DIR, project_id)
        os.makedirs(project_dir, exist_ok=True)

        state_path = os.path.join(project_dir, "project_state.json")
        content = json.dumps(project.to_dict(), indent=2)
        atomic_write(state_path, content)

    # ── Completion Detection & Advancement ──────────────────────────────

    def check_completion(self, project_id: str) -> bool:
        """
        Check if the current agent has completed its work.
        If complete: validate artifact, check scores, advance phase, dispatch next.
        Returns True if phase was advanced.
        """
        project = self.projects[project_id]
        project_dir = os.path.join(PROJECTS_DIR, project_id)

        if not check_completion(project_dir, project.phase):
            return False

        logger.info("Completion detected for %s in phase %s", project_id, project.phase)

        # Validate artifact
        is_valid, error = validate_artifact(project_dir, project.phase)
        if not is_valid:
            logger.warning("Artifact validation failed for %s: %s", project_id, error)
            record_error(project)
            notify_error(project.name, "ArtifactValidation", error)
            self.save_project(project_id)
            return False

        # Parse status for score
        try:
            status = parse_status(project_dir, project.phase)
            score = status.get("score")
            logger.info("Agent score for %s: %s", project_id, score)
        except (ValueError, FileNotFoundError) as e:
            logger.warning("Failed to parse status for %s: %s", project_id, e)
            record_error(project)
            notify_error(project.name, "StatusParse", str(e))
            self.save_project(project_id)
            return False

        # Check scores for warnings (R1 consolidation point)
        if project.phase == "R1_CONSOLIDATE":
            issue, scores = check_scores(project_dir)
            if issue:
                logger.warning("Score issue for %s: %s — %s", project_id, issue, scores)
                notify_error(project.name, "ScoreIssue",
                             f"{issue}: {json.dumps(scores)}")

        # Advance phase
        self.advance_phase(project_id)
        return True

    def advance_phase(self, project_id: str) -> None:
        """Core phase advancement: cleanup, advance, dispatch, notify."""
        project = self.projects[project_id]
        project_dir = os.path.join(PROJECTS_DIR, project_id)

        # Clean up old status file
        old_status = PHASE_STATUS_FILES.get(project.phase)
        if old_status:
            old_status_path = os.path.join(project_dir, old_status)
            if os.path.exists(old_status_path):
                os.remove(old_status_path)
                logger.debug("Cleaned up old status file: %s", old_status_path)

        # Reset error tracking
        reset_errors(project)

        # Notify Eddie about completed phase (rate-limited)
        old_phase = project.phase
        agent = PHASE_OWNERS.get(old_phase, "unknown")
        if self.rate_limiter.can_notify(project.name):
            msg = notify_phase_complete(project.name, old_phase, agent)
            logger.info("Notification: %s", msg)

        # Advance project phase
        project.advance()
        self.save_project(project_id)

        # Dispatch next agent if applicable
        next_agent = PHASE_OWNERS.get(project.phase, "unknown")
        if next_agent not in ("orchestrator",):
            self.dispatch_current_agent(project_id)

        # Special handling for READY_FOR_BUILD
        if project.phase == "READY_FOR_BUILD":
            if self.rate_limiter.can_notify(project.name):
                msg = notify_ready_for_build(project.name)
                logger.info("Notification: %s", msg)

    # ── Agent Dispatch ─────────────────────────────────────────────────

    def dispatch_current_agent(self, project_id: str) -> None:
        """Determine agent type and dispatch via Hermes cron or Tripp file drop."""
        project = self.projects[project_id]
        agent = PHASE_OWNERS.get(project.phase, "unknown")

        if agent in ("orchestrator", "codex"):
            logger.debug("Phase %s does not need agent dispatch (owner=%s)", project.phase, agent)
            return

        project_dir = os.path.join(PROJECTS_DIR, project_id)

        try:
            info = dispatch_agent(project)
            logger.info("Dispatched agent %s for %s (method=%s)", agent, project_id, info.get("method"))

            # Store cron info in project state for later lookup
            if info.get("method") == "hermes_cron" and "job" in info:
                if "cron_jobs" not in project.__dict__:
                    # Extend project dict with cron_jobs tracking
                    pass
                # We store it on the project's model dict for serialization
                project.model["_last_dispatch"] = info["job"]

            self.save_project(project_id)

        except Exception as e:
            logger.error("Failed to dispatch agent for %s: %s", project_id, e)
            notify_error(project.name, "DispatchFailed", str(e))

    # ── Timeout Handling ───────────────────────────────────────────────

    def check_timeouts(self) -> None:
        """For each active project, check if the current phase has timed out."""
        now = datetime.datetime.utcnow()

        for project_id, project in self.projects.items():
            # Skip terminal phases
            if project.phase in ("STORED", "TRASHED", "CANCELLED"):
                continue

            # Skip phases without timeouts
            timeout_minutes = PHASE_TIMEOUTS.get(project.phase)
            if timeout_minutes is None:
                continue

            # Check if phase has timed out
            phase_started = self._parse_time(project.phase_started_at)
            if phase_started is None:
                continue

            elapsed = (now - phase_started).total_seconds() / 60.0
            if elapsed <= timeout_minutes:
                continue

            # Timeout detected
            agent = PHASE_OWNERS.get(project.phase, "unknown")
            logger.warning(
                "Timeout for %s: phase %s exceeded %d min (elapsed: %.1f min)",
                project_id, project.phase, timeout_minutes, elapsed,
            )

            if project.error_tracking.get("alert_suppressed"):
                logger.info("Alert suppressed for %s — %d consecutive errors",
                            project_id, project.error_tracking["consecutive_errors"])
                continue

            record_error(project)
            self.save_project(project_id)

            msg = notify_timeout(project.name, project.phase, agent)
            logger.info("Notification: %s", msg)

    def check_idle_timeout(self, project_id: str) -> None:
        """At READY_FOR_BUILD: 48h → reminder, 7d → auto-store."""
        project = self.projects[project_id]

        if project.phase != AuditPhase.READY_FOR_BUILD.value:
            return

        phase_started = self._parse_time(project.phase_started_at)
        if phase_started is None:
            return

        now = datetime.datetime.utcnow()
        elapsed_hours = (now - phase_started).total_seconds() / 3600.0
        elapsed_days = elapsed_hours / 24.0

        # 7 days → auto-store
        if elapsed_days >= IDLE_AUTOSTORE_DAYS:
            logger.info("Auto-storing %s after %.1f days idle", project_id, elapsed_days)
            project.phase = AuditPhase.STORED.value
            project.updated_at = datetime.datetime.utcnow().isoformat() + "Z"
            self.save_project(project_id)

            if self.rate_limiter.can_notify(project.name):
                msg = notify_idle_autostore(project.name)
                logger.info("Notification: %s", msg)
            return

        # 48 hours → reminder
        if elapsed_hours >= IDLE_REMINDER_HOURS:
            if self.rate_limiter.can_notify(project.name):
                msg = notify_idle_reminder(project.name, round(elapsed_hours, 1))
                logger.info("Notification: %s", msg)

    def check_trash_timers(self) -> None:
        """For TRASHED projects: 13d → warning, 20d → auto-delete."""
        now = datetime.datetime.utcnow()

        for project_id, project in list(self.projects.items()):
            if project.phase != AuditPhase.TRASHED.value:
                continue

            trashed_at = self._parse_time(project.trashed_at)
            if trashed_at is None:
                continue

            elapsed_days = (now - trashed_at).days

            # 20 days → auto-delete
            if elapsed_days >= TRASH_RETENTION_DAYS:
                logger.info("Auto-deleting %s after %d days in trash", project_id, elapsed_days)

                # Remove project directory
                project_dir = os.path.join(PROJECTS_DIR, project_id)
                if os.path.exists(project_dir):
                    import shutil
                    shutil.rmtree(project_dir)
                    logger.info("Removed project directory: %s", project_dir)

                del self.projects[project_id]
                continue

            # 13 days → warning
            if elapsed_days >= TRASH_WARNING_DAYS:
                days_left = TRASH_RETENTION_DAYS - elapsed_days
                if self.rate_limiter.can_notify(project.name):
                    msg = notify_trash_warning(project.name, days_left)
                    logger.info("Notification: %s", msg)

    # ── Heartbeat ──────────────────────────────────────────────────────

    def write_heartbeat(self) -> None:
        """Write timestamp to .orchestrator_heartbeat in PROJECTS_DIR."""
        heartbeat_path = os.path.join(PROJECTS_DIR, ".orchestrator_heartbeat")
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        atomic_write(heartbeat_path, timestamp)

    # ── Main Loop ──────────────────────────────────────────────────────

    def run_once(self) -> None:
        """Single iteration of the main loop."""
        logger.debug("Running orchestrator cycle")

        # Write heartbeat
        try:
            self.write_heartbeat()
        except Exception as e:
            logger.error("Failed to write heartbeat: %s", e)

        # Check completions for active projects
        for project_id in list(self.projects.keys()):
            project = self.projects.get(project_id)
            if project is None:
                continue
            if project.phase in ("PLANNING", "READY_FOR_AUDIT", "STORED", "TRASHED", "CANCELLED"):
                continue

            try:
                self.check_completion(project_id)
            except Exception as e:
                logger.error("Error checking completion for %s: %s", project_id, e)

        # Check timeouts
        try:
            self.check_timeouts()
        except Exception as e:
            logger.error("Error checking timeouts: %s", e)

        # Check idle timeouts
        for project_id in list(self.projects.keys()):
            try:
                self.check_idle_timeout(project_id)
            except Exception as e:
                logger.error("Error checking idle timeout for %s: %s", project_id, e)

        # Check trash timers
        try:
            self.check_trash_timers()
        except Exception as e:
            logger.error("Error checking trash timers: %s", e)

    def run(self, max_iterations: int | None = None) -> None:
        """
        Main loop: call run_once() every MARKER_CHECK_INTERVAL seconds.

        Args:
            max_iterations: If set, run this many cycles then stop (for testing).
        """
        iteration = 0
        logger.info("Starting orchestrator loop (interval=%ds)", MARKER_CHECK_INTERVAL)

        while True:
            try:
                self.run_once()
            except Exception as e:
                logger.error("Unhandled exception in run_once: %s", e)

            iteration += 1
            if max_iterations is not None and iteration >= max_iterations:
                logger.info("Reached max_iterations=%d, stopping", max_iterations)
                break

            time.sleep(MARKER_CHECK_INTERVAL)

    # ── Internal Helpers ───────────────────────────────────────────────

    @staticmethod
    def _parse_time(iso_str: str | None) -> datetime.datetime | None:
        """Parse an ISO-8601 timestamp string, returning None on failure."""
        if not iso_str:
            return None
        s = iso_str.rstrip("Z")
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None
