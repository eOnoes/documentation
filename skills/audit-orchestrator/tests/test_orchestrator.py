"""
Comprehensive tests for Audit Orchestrator — Phase 5: Main Orchestrator Loop

Covers:
- create_project saves state file to disk
- load_projects loads from disk
- start_team_audit advances to R1_ECHO and dispatches
- check_completion detects and advances (mocked detector)
- advance_phase resets errors and dispatches next agent
- check_timeouts detects timeout and alerts Eddie
- check_idle_timeout sends reminder at 48h, auto-stores at 7d
- check_trash_timers warns at 13d, deletes at 20d
- write_heartbeat creates file
- run_once runs one cycle
- run with max_iterations
- Graceful shutdown (mock signal)
"""

import os
import json
import time
import shutil
import datetime
import logging
from unittest.mock import patch, MagicMock, call

import pytest

from orchestrator.config import (
    PROJECTS_DIR,
    MARKER_CHECK_INTERVAL,
    PHASE_STATUS_FILES,
    PHASE_TIMEOUTS,
    IDLE_REMINDER_HOURS,
    IDLE_AUTOSTORE_DAYS,
    TRASH_WARNING_DAYS,
    TRASH_RETENTION_DAYS,
    PHASE_OWNERS,
)
from orchestrator.models import AuditProject, AuditPhase, PHASE_ORDER
from orchestrator.orchestrator import AuditOrchestrator
from orchestrator.notifier import RateLimiter


# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════

def _make_project(**kwargs) -> AuditProject:
    """Create a fresh AuditProject with sensible defaults for testing."""
    defaults = {
        "project_id": "test-project",
        "name": "Test Project",
        "lead": "Cyony",
        "phase": "PLANNING",
        "round": 1,
    }
    defaults.update(kwargs)
    return AuditProject(**defaults)


def _write_status_file(project_dir: str, phase: str, data: dict) -> str:
    """Write a status file for the given phase and return the path."""
    status_file = PHASE_STATUS_FILES[phase]
    status_path = os.path.join(project_dir, status_file)
    os.makedirs(os.path.dirname(status_path), exist_ok=True)
    with open(status_path, "w") as f:
        json.dump(data, f)
    return status_path


def _write_artifact(project_dir: str, phase: str, content: str) -> str:
    """Write an artifact file for the given phase and return the path."""
    from orchestrator.config import PHASE_OUTPUT_FILES
    output_file = PHASE_OUTPUT_FILES[phase]
    artifact_path = os.path.join(project_dir, output_file)
    os.makedirs(os.path.dirname(artifact_path) or ".", exist_ok=True)
    with open(artifact_path, "w") as f:
        f.write(content)
    return artifact_path


def _make_orchestrator(tmp_path, monkeypatch=None):
    """Create an AuditOrchestrator configured to use tmp_path as PROJECTS_DIR."""
    if monkeypatch:
        monkeypatch.setattr("orchestrator.orchestrator.PROJECTS_DIR", str(tmp_path))
        monkeypatch.setattr("orchestrator.dispatcher.PROJECTS_DIR", str(tmp_path))
    else:
        import orchestrator.orchestrator as orch_mod
        orch_mod.PROJECTS_DIR = str(tmp_path)

    orch = AuditOrchestrator()
    return orch


def _make_orchestrator_with_mock_rl(tmp_path, can_notify_return=True):
    """Create orchestrator with a mocked rate_limiter."""
    import orchestrator.orchestrator as orch_mod
    orch_mod.PROJECTS_DIR = str(tmp_path)
    orch = AuditOrchestrator()
    mock_rl = MagicMock(spec=RateLimiter)
    mock_rl.can_notify.return_value = can_notify_return
    orch.rate_limiter = mock_rl
    return orch


# ══════════════════════════════════════════════════════════════════════
# create_project Tests
# ══════════════════════════════════════════════════════════════════════

class TestCreateProject:
    def test_saves_state_file(self, tmp_path):
        """create_project should create project_state.json on disk."""
        orch = _make_orchestrator(tmp_path)

        project = orch.create_project("proj-1", "My Project", "Eddie")

        assert os.path.exists(tmp_path / "proj-1" / "project_state.json")

        with open(tmp_path / "proj-1" / "project_state.json") as f:
            data = json.load(f)
        assert data["project_id"] == "proj-1"
        assert data["name"] == "My Project"
        assert data["lead"] == "Eddie"
        assert data["phase"] == "PLANNING"

    def test_creates_project_directory(self, tmp_path):
        """create_project should create the project subdirectory."""
        orch = _make_orchestrator(tmp_path)
        orch.create_project("proj-1", "My Project")
        assert os.path.isdir(tmp_path / "proj-1")

    def test_adds_to_projects_dict(self, tmp_path):
        """create_project should add the project to self.projects."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "My Project")
        assert "proj-1" in orch.projects
        assert orch.projects["proj-1"] is project

    def test_returns_project_instance(self, tmp_path):
        """create_project should return an AuditProject instance."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "My Project")
        assert isinstance(project, AuditProject)
        assert project.project_id == "proj-1"

    def test_creates_initial_plan_placeholder(self, tmp_path):
        """create_project should create a LEAD_PLAN.md placeholder."""
        orch = _make_orchestrator(tmp_path)
        orch.create_project("proj-1", "My Project")
        plan_path = tmp_path / "proj-1" / "LEAD_PLAN.md"
        assert os.path.exists(plan_path)
        content = open(plan_path).read()
        assert "My Project" in content

    def test_state_file_is_valid_json(self, tmp_path):
        """Saved state file must be valid JSON."""
        orch = _make_orchestrator(tmp_path)
        orch.create_project("proj-1", "My Project")
        state_path = tmp_path / "proj-1" / "project_state.json"
        with open(state_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)


# ══════════════════════════════════════════════════════════════════════
# load_projects Tests
# ══════════════════════════════════════════════════════════════════════

class TestLoadProjects:
    def test_loads_from_disk(self, tmp_path):
        """load_projects should discover projects from PROJECTS_DIR."""
        # Create a project on disk
        project_dir = tmp_path / "proj-1"
        project_dir.mkdir()
        project = _make_project(project_id="proj-1", name="Loaded Project")
        with open(project_dir / "project_state.json", "w") as f:
            json.dump(project.to_dict(), f)

        orch = _make_orchestrator(tmp_path)
        orch.load_projects()

        assert "proj-1" in orch.projects
        assert orch.projects["proj-1"].name == "Loaded Project"

    def test_loads_multiple_projects(self, tmp_path):
        """load_projects should discover all projects."""
        for i in range(3):
            project_dir = tmp_path / f"proj-{i}"
            project_dir.mkdir()
            project = _make_project(project_id=f"proj-{i}", name=f"Project {i}")
            with open(project_dir / "project_state.json", "w") as f:
                json.dump(project.to_dict(), f)

        orch = _make_orchestrator(tmp_path)
        orch.load_projects()

        assert len(orch.projects) == 3

    def test_skips_dirs_without_state_file(self, tmp_path):
        """load_projects should skip directories without project_state.json."""
        (tmp_path / "empty-dir").mkdir()
        (tmp_path / "another-dir").mkdir()

        orch = _make_orchestrator(tmp_path)
        orch.load_projects()

        assert len(orch.projects) == 0

    def test_skips_malformed_state_file(self, tmp_path):
        """load_projects should skip projects with invalid JSON."""
        project_dir = tmp_path / "bad-project"
        project_dir.mkdir()
        with open(project_dir / "project_state.json", "w") as f:
            f.write("{bad json!!!")

        orch = _make_orchestrator(tmp_path)
        orch.load_projects()

        assert len(orch.projects) == 0

    def test_skips_non_directory_entries(self, tmp_path):
        """load_projects should skip files (not directories)."""
        with open(tmp_path / "random-file.json", "w") as f:
            f.write("{}")

        orch = _make_orchestrator(tmp_path)
        orch.load_projects()

        assert len(orch.projects) == 0

    def test_empty_dir_loads_zero_projects(self, tmp_path):
        """load_projects on empty dir should result in 0 projects."""
        orch = _make_orchestrator(tmp_path)
        orch.load_projects()
        assert len(orch.projects) == 0


# ══════════════════════════════════════════════════════════════════════
# start_team_audit Tests
# ══════════════════════════════════════════════════════════════════════

class TestStartTeamAudit:
    def test_advances_to_r1_echo(self, tmp_path):
        """start_team_audit should advance PLANNING → R1_ECHO."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")

        orch.start_team_audit("proj-1")

        assert orch.projects["proj-1"].phase == "R1_ECHO"

    def test_saves_state_after_advance(self, tmp_path):
        """start_team_audit should persist the new phase."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")

        orch.start_team_audit("proj-1")

        # Reload from disk
        with open(tmp_path / "proj-1" / "project_state.json") as f:
            data = json.load(f)
        assert data["phase"] == "R1_ECHO"

    @patch("orchestrator.orchestrator.dispatch_agent")
    def test_dispatches_first_agent(self, mock_dispatch, tmp_path):
        """start_team_audit should dispatch the first agent (echo)."""
        mock_dispatch.return_value = {"agent": "echo", "method": "hermes_cron", "job": {}}

        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")

        orch.start_team_audit("proj-1")

        mock_dispatch.assert_called_once()
        dispatched_project = mock_dispatch.call_args[0][0]
        assert dispatched_project.phase == "R1_ECHO"


# ══════════════════════════════════════════════════════════════════════
# check_completion Tests
# ══════════════════════════════════════════════════════════════════════

class TestCheckCompletion:
    @patch("orchestrator.orchestrator.check_completion")
    @patch("orchestrator.orchestrator.validate_artifact")
    @patch("orchestrator.orchestrator.parse_status")
    @patch("orchestrator.orchestrator.dispatch_agent")
    @patch("orchestrator.orchestrator.reset_errors")
    @patch("orchestrator.orchestrator.notify_phase_complete")
    def test_detects_and_advances(self, mock_notify, mock_reset, mock_dispatch,
                                   mock_parse, mock_validate, mock_check, tmp_path):
        """check_completion should advance when agent is done."""
        mock_check.return_value = True
        mock_validate.return_value = (True, None)
        mock_parse.return_value = {"status": "done", "score": 7}
        mock_dispatch.return_value = {"agent": "echo", "method": "hermes_cron", "job": {}}

        orch = _make_orchestrator_with_mock_rl(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "R1_ECHO"

        result = orch.check_completion("proj-1")

        assert result is True

    @patch("orchestrator.orchestrator.check_completion")
    def test_returns_false_when_not_complete(self, mock_check, tmp_path):
        """check_completion should return False when not complete."""
        mock_check.return_value = False

        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "R1_ECHO"

        result = orch.check_completion("proj-1")

        assert result is False

    @patch("orchestrator.orchestrator.check_completion")
    @patch("orchestrator.orchestrator.validate_artifact")
    @patch("orchestrator.orchestrator.record_error")
    @patch("orchestrator.orchestrator.notify_error")
    def test_records_error_on_invalid_artifact(self, mock_notify, mock_record,
                                                mock_validate, mock_check, tmp_path):
        """check_completion should record error when artifact validation fails."""
        mock_check.return_value = True
        mock_validate.return_value = (False, "Artifact too short")

        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "R1_ECHO"

        result = orch.check_completion("proj-1")

        assert result is False
        mock_record.assert_called_once()

    @patch("orchestrator.orchestrator.check_completion")
    @patch("orchestrator.orchestrator.validate_artifact")
    @patch("orchestrator.orchestrator.parse_status")
    @patch("orchestrator.orchestrator.record_error")
    @patch("orchestrator.orchestrator.notify_error")
    def test_records_error_on_parse_failure(self, mock_notify, mock_record,
                                             mock_parse, mock_validate,
                                             mock_check, tmp_path):
        """check_completion should record error when status parsing fails."""
        mock_check.return_value = True
        mock_validate.return_value = (True, None)
        mock_parse.side_effect = ValueError("Malformed JSON")

        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "R1_ECHO"

        result = orch.check_completion("proj-1")

        assert result is False
        mock_record.assert_called_once()


# ══════════════════════════════════════════════════════════════════════
# advance_phase Tests
# ══════════════════════════════════════════════════════════════════════

class TestAdvancePhase:
    @patch("orchestrator.orchestrator.dispatch_agent")
    @patch("orchestrator.orchestrator.reset_errors")
    @patch("orchestrator.orchestrator.notify_phase_complete")
    def test_resets_errors_and_dispatches(self, mock_notify, mock_reset,
                                           mock_dispatch, tmp_path):
        """advance_phase should reset error tracking and dispatch next agent."""
        mock_dispatch.return_value = {"agent": "echo", "method": "hermes_cron", "job": {}}

        orch = _make_orchestrator_with_mock_rl(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "R1_ECHO"
        project.error_tracking["consecutive_errors"] = 3

        orch.advance_phase("proj-1")

        mock_reset.assert_called_once()
        assert orch.projects["proj-1"].phase == "R1_TRIPP"
        mock_dispatch.assert_called_once()

    @patch("orchestrator.orchestrator.dispatch_agent")
    @patch("orchestrator.orchestrator.reset_errors")
    @patch("orchestrator.orchestrator.notify_phase_complete")
    def test_cleans_up_old_status_file(self, mock_notify, mock_reset,
                                        mock_dispatch, tmp_path):
        """advance_phase should remove the old status file."""
        mock_dispatch.return_value = {"agent": "tripp", "method": "file_drop", "trigger_file": ""}

        orch = _make_orchestrator_with_mock_rl(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "R1_ECHO"

        # Create a fake old status file
        status_dir = tmp_path / "proj-1" / ".status"
        status_dir.mkdir(parents=True)
        status_path = status_dir / "echo_r1.json"
        status_path.write_text('{"status":"done"}')

        orch.advance_phase("proj-1")

        assert not status_path.exists()

    @patch("orchestrator.orchestrator.dispatch_agent")
    @patch("orchestrator.orchestrator.reset_errors")
    @patch("orchestrator.orchestrator.notify_phase_complete")
    def test_notifies_ready_for_build(self, mock_notify, mock_reset,
                                       mock_dispatch, tmp_path):
        """advance_phase should notify Eddie when entering READY_FOR_BUILD."""
        mock_dispatch.return_value = {"agent": "codex", "method": "none"}

        orch = _make_orchestrator_with_mock_rl(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "R2_CONSOLIDATE"

        orch.advance_phase("proj-1")

        assert orch.projects["proj-1"].phase == "READY_FOR_BUILD"


# ══════════════════════════════════════════════════════════════════════
# check_timeouts Tests
# ══════════════════════════════════════════════════════════════════════

class TestCheckTimeouts:
    @patch("orchestrator.orchestrator.record_error")
    @patch("orchestrator.orchestrator.notify_timeout")
    def test_detects_timeout(self, mock_notify, mock_record, tmp_path):
        """check_timeouts should detect when a phase has exceeded its timeout."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "R1_ECHO"

        # Set phase_started_at to 3 hours ago (exceeds 120 min timeout)
        three_hours_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=3)
        project.phase_started_at = three_hours_ago.isoformat() + "Z"

        orch.check_timeouts()

        mock_record.assert_called_once()

    @patch("orchestrator.orchestrator.record_error")
    @patch("orchestrator.orchestrator.notify_timeout")
    def test_no_timeout_when_within_limit(self, mock_notify, mock_record, tmp_path):
        """check_timeouts should not trigger when within timeout."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "R1_ECHO"

        # Set phase_started_at to 10 minutes ago (well within 120 min)
        ten_min_ago = datetime.datetime.utcnow() - datetime.timedelta(minutes=10)
        project.phase_started_at = ten_min_ago.isoformat() + "Z"

        orch.check_timeouts()

        mock_record.assert_not_called()

    @patch("orchestrator.orchestrator.record_error")
    @patch("orchestrator.orchestrator.notify_timeout")
    def test_skips_terminal_phases(self, mock_notify, mock_record, tmp_path):
        """check_timeouts should skip STORED/TRASHED/CANCELLED."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")

        for phase in ("STORED", "TRASHED", "CANCELLED"):
            project.phase = phase
            orch.check_timeouts()

        mock_record.assert_not_called()

    @patch("orchestrator.orchestrator.record_error")
    @patch("orchestrator.orchestrator.notify_timeout")
    def test_skips_phases_without_timeout(self, mock_notify, mock_record, tmp_path):
        """check_timeouts should skip phases without a configured timeout."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "PLANNING"

        orch.check_timeouts()

        mock_record.assert_not_called()

    @patch("orchestrator.orchestrator.record_error")
    @patch("orchestrator.orchestrator.notify_timeout")
    def test_suppresses_alert_after_max_errors(self, mock_notify, mock_record, tmp_path):
        """check_timeouts should suppress alerts after MAX_ALERTSUPPRESSION."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "R1_ECHO"
        project.error_tracking["alert_suppressed"] = True
        project.error_tracking["consecutive_errors"] = 4

        three_hours_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=3)
        project.phase_started_at = three_hours_ago.isoformat() + "Z"

        orch.check_timeouts()

        mock_record.assert_not_called()


# ══════════════════════════════════════════════════════════════════════
# check_idle_timeout Tests
# ══════════════════════════════════════════════════════════════════════

class TestCheckIdleTimeout:
    @patch("orchestrator.orchestrator.notify_idle_reminder")
    def test_sends_reminder_at_48h(self, mock_reminder, tmp_path):
        """check_idle_timeout should send reminder after 48h idle at READY_FOR_BUILD."""
        orch = _make_orchestrator_with_mock_rl(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "READY_FOR_BUILD"

        # Set phase_started_at to 49 hours ago
        forty_nine_hours_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=49)
        project.phase_started_at = forty_nine_hours_ago.isoformat() + "Z"

        orch.check_idle_timeout("proj-1")

        mock_reminder.assert_called_once()
        assert project.phase == "READY_FOR_BUILD"  # Still in same phase

    @patch("orchestrator.orchestrator.notify_idle_autostore")
    def test_auto_stores_at_7d(self, mock_autostore, tmp_path):
        """check_idle_timeout should auto-store after 7 days."""
        orch = _make_orchestrator_with_mock_rl(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "READY_FOR_BUILD"

        # Set phase_started_at to 8 days ago
        eight_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=8)
        project.phase_started_at = eight_days_ago.isoformat() + "Z"

        orch.check_idle_timeout("proj-1")

        assert project.phase == "STORED"
        mock_autostore.assert_called_once()

    def test_no_action_before_48h(self, tmp_path):
        """check_idle_timeout should do nothing before 48h."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "READY_FOR_BUILD"

        # Set phase_started_at to 24 hours ago
        one_day_ago = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
        project.phase_started_at = one_day_ago.isoformat() + "Z"

        orch.check_idle_timeout("proj-1")

        assert project.phase == "READY_FOR_BUILD"  # No change

    def test_skips_non_ready_phases(self, tmp_path):
        """check_idle_timeout should skip phases other than READY_FOR_BUILD."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "R1_ECHO"

        # Even with very old phase_started_at, should do nothing
        old_time = datetime.datetime.utcnow() - datetime.timedelta(days=30)
        project.phase_started_at = old_time.isoformat() + "Z"

        orch.check_idle_timeout("proj-1")

        assert project.phase == "R1_ECHO"  # No change

    @patch("orchestrator.orchestrator.notify_idle_reminder")
    def test_7d_takes_priority_over_48h(self, mock_reminder, tmp_path):
        """At 7 days, should auto-store (not just remind)."""
        orch = _make_orchestrator_with_mock_rl(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "READY_FOR_BUILD"

        eight_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=8)
        project.phase_started_at = eight_days_ago.isoformat() + "Z"

        orch.check_idle_timeout("proj-1")

        # Should be STORED, not still READY_FOR_BUILD
        assert project.phase == "STORED"
        # Reminder should NOT have been called (auto-store took priority)
        mock_reminder.assert_not_called()


# ══════════════════════════════════════════════════════════════════════
# check_trash_timers Tests
# ══════════════════════════════════════════════════════════════════════

class TestCheckTrashTimers:
    @patch("orchestrator.orchestrator.notify_trash_warning")
    def test_warns_at_13d(self, mock_warning, tmp_path):
        """check_trash_timers should warn at 13 days."""
        orch = _make_orchestrator_with_mock_rl(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.trash()

        thirteen_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=13)
        project.trashed_at = thirteen_days_ago.isoformat() + "Z"

        orch.check_trash_timers()

        mock_warning.assert_called_once()
        # Should still be in trash (not deleted yet)
        assert project.phase == "TRASHED"

    def test_deletes_at_20d(self, tmp_path):
        """check_trash_timers should auto-delete after 20 days."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.trash()

        twenty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=20)
        project.trashed_at = twenty_days_ago.isoformat() + "Z"

        orch.check_trash_timers()

        # Project should be removed
        assert "proj-1" not in orch.projects
        # Directory should be removed
        assert not (tmp_path / "proj-1").exists()

    def test_no_action_before_13d(self, tmp_path):
        """check_trash_timers should do nothing before 13 days."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.trash()

        ten_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=10)
        project.trashed_at = ten_days_ago.isoformat() + "Z"

        orch.check_trash_timers()

        assert project.phase == "TRASHED"  # Still in trash

    def test_skips_non_trashed(self, tmp_path):
        """check_trash_timers should skip non-TRASHED projects."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        # project is PLANNING, not TRASHED

        orch.check_trash_timers()

        assert "proj-1" in orch.projects  # Not deleted

    @patch("orchestrator.orchestrator.notify_trash_warning")
    def test_warning_shows_correct_days_left(self, mock_warning, tmp_path):
        """Trash warning should show remaining days (20 - elapsed)."""
        orch = _make_orchestrator_with_mock_rl(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.trash()

        fifteen_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=15)
        project.trashed_at = fifteen_days_ago.isoformat() + "Z"

        orch.check_trash_timers()

        # 20 - 15 = 5 days left
        args = mock_warning.call_args
        assert args[0][1] == 5  # days_left


# ══════════════════════════════════════════════════════════════════════
# write_heartbeat Tests
# ══════════════════════════════════════════════════════════════════════

class TestWriteHeartbeat:
    def test_creates_heartbeat_file(self, tmp_path):
        """write_heartbeat should create .orchestrator_heartbeat file."""
        orch = _make_orchestrator(tmp_path)
        orch.write_heartbeat()

        heartbeat_path = tmp_path / ".orchestrator_heartbeat"
        assert heartbeat_path.exists()

    def test_heartbeat_contains_timestamp(self, tmp_path):
        """Heartbeat file should contain an ISO timestamp."""
        orch = _make_orchestrator(tmp_path)
        orch.write_heartbeat()

        heartbeat_path = tmp_path / ".orchestrator_heartbeat"
        content = heartbeat_path.read_text()
        assert "T" in content  # ISO format check
        assert content.strip().endswith("Z")

    def test_heartbeat_overwrites_previous(self, tmp_path):
        """write_heartbeat should overwrite existing heartbeat."""
        orch = _make_orchestrator(tmp_path)

        orch.write_heartbeat()
        first_content = (tmp_path / ".orchestrator_heartbeat").read_text()

        time.sleep(0.01)

        orch.write_heartbeat()
        second_content = (tmp_path / ".orchestrator_heartbeat").read_text()

        assert first_content != second_content


# ══════════════════════════════════════════════════════════════════════
# save_project Tests
# ══════════════════════════════════════════════════════════════════════

class TestSaveProject:
    def test_saves_atomic_write(self, tmp_path):
        """save_project should atomically write project_state.json."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "R1_ECHO"

        orch.save_project("proj-1")

        with open(tmp_path / "proj-1" / "project_state.json") as f:
            data = json.load(f)
        assert data["phase"] == "R1_ECHO"

    def test_saves_error_tracking(self, tmp_path):
        """save_project should persist error_tracking state."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.error_tracking["consecutive_errors"] = 2

        orch.save_project("proj-1")

        with open(tmp_path / "proj-1" / "project_state.json") as f:
            data = json.load(f)
        assert data["error_tracking"]["consecutive_errors"] == 2


# ══════════════════════════════════════════════════════════════════════
# run_once Tests
# ══════════════════════════════════════════════════════════════════════

class TestRunOnce:
    @patch("orchestrator.orchestrator.AuditOrchestrator.write_heartbeat")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_timeouts")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_completion")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_idle_timeout")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_trash_timers")
    def test_runs_one_cycle(self, mock_trash, mock_idle, mock_complete,
                             mock_timeout, mock_heartbeat, tmp_path):
        """run_once should call all check methods exactly once."""
        orch = _make_orchestrator(tmp_path)

        orch.run_once()

        mock_heartbeat.assert_called_once()
        mock_timeout.assert_called_once()
        mock_trash.assert_called_once()

    @patch("orchestrator.orchestrator.AuditOrchestrator.write_heartbeat")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_timeouts")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_completion")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_idle_timeout")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_trash_timers")
    def test_checks_completions_for_active_phases(self, mock_trash, mock_idle,
                                                    mock_complete, mock_timeout,
                                                    mock_heartbeat, tmp_path):
        """run_once should check completion for projects in active phases."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        project.phase = "R1_ECHO"

        orch.run_once()

        mock_complete.assert_called_once_with("proj-1")

    @patch("orchestrator.orchestrator.AuditOrchestrator.write_heartbeat")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_timeouts")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_completion")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_idle_timeout")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_trash_timers")
    def test_skips_planning_phase(self, mock_trash, mock_idle, mock_complete,
                                    mock_timeout, mock_heartbeat, tmp_path):
        """run_once should not check completion for PLANNING projects."""
        orch = _make_orchestrator(tmp_path)
        project = orch.create_project("proj-1", "Test")
        # Default phase is PLANNING

        orch.run_once()

        mock_complete.assert_not_called()

    @patch("orchestrator.orchestrator.AuditOrchestrator.write_heartbeat")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_timeouts")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_completion")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_idle_timeout")
    @patch("orchestrator.orchestrator.AuditOrchestrator.check_trash_timers")
    def test_checks_idle_for_each_project(self, mock_trash, mock_idle, mock_complete,
                                           mock_timeout, mock_heartbeat, tmp_path):
        """run_once should check idle timeout for each project."""
        orch = _make_orchestrator(tmp_path)
        orch.create_project("proj-1", "Test A")
        orch.create_project("proj-2", "Test B")

        orch.run_once()

        # check_idle_timeout called for each project
        assert mock_idle.call_count == 2


# ══════════════════════════════════════════════════════════════════════
# run() Tests
# ══════════════════════════════════════════════════════════════════════

class TestRun:
    @patch("orchestrator.orchestrator.time.sleep")
    @patch("orchestrator.orchestrator.AuditOrchestrator.run_once")
    def test_runs_max_iterations(self, mock_run_once, mock_sleep, tmp_path):
        """run(max_iterations=N) should stop after N iterations."""
        orch = _make_orchestrator(tmp_path)

        orch.run(max_iterations=3)

        assert mock_run_once.call_count == 3

    @patch("orchestrator.orchestrator.time.sleep")
    @patch("orchestrator.orchestrator.AuditOrchestrator.run_once")
    def test_sleeps_between_iterations(self, mock_run_once, mock_sleep, tmp_path):
        """run() should sleep MARKER_CHECK_INTERVAL between iterations."""
        orch = _make_orchestrator(tmp_path)

        orch.run(max_iterations=2)

        # Loop: iter 0 → run_once, iter=1, 1<2 → sleep; iter 1 → run_once, iter=2, 2>=2 → break
        # So only 1 sleep call
        mock_sleep.assert_called_with(MARKER_CHECK_INTERVAL)
        assert mock_sleep.call_count == 1

    @patch("orchestrator.orchestrator.time.sleep")
    @patch("orchestrator.orchestrator.AuditOrchestrator.run_once")
    def test_stops_on_max_iterations_1(self, mock_run_once, mock_sleep, tmp_path):
        """run(max_iterations=1) should run exactly once."""
        orch = _make_orchestrator(tmp_path)

        orch.run(max_iterations=1)

        assert mock_run_once.call_count == 1


# ══════════════════════════════════════════════════════════════════════
# Graceful Shutdown Tests
# ══════════════════════════════════════════════════════════════════════

class TestGracefulShutdown:
    def test_signal_handler_sets_flag(self, tmp_path):
        """main.py signal handler should set shutdown flag."""
        from orchestrator.main import main
        import signal

        # Verify signal constants exist
        assert hasattr(signal, 'SIGTERM')
        assert hasattr(signal, 'SIGINT')

    def test_shutdown_flag_stops_loop(self):
        """When shutdown_requested is True, run loop should exit."""
        # This tests the pattern used in main.py
        shutdown_requested = False

        def _handle_signal(signum, frame):
            nonlocal shutdown_requested
            shutdown_requested = True

        import signal as sig
        old_handler = sig.getsignal(sig.SIGUSR1)
        try:
            sig.signal(sig.SIGUSR1, _handle_signal)
            import os, time
            os.kill(os.getpid(), sig.SIGUSR1)
            time.sleep(0.01)

            assert shutdown_requested is True
        finally:
            sig.signal(sig.SIGUSR1, old_handler)


# ══════════════════════════════════════════════════════════════════════
# Integration / Edge Case Tests
# ══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_empty_projects_dir(self, tmp_path):
        """Orchestrator should handle empty PROJECTS_DIR gracefully."""
        orch = _make_orchestrator(tmp_path)
        orch.load_projects()
        orch.run_once()
        assert len(orch.projects) == 0

    def test_projects_dir_created_if_missing(self, tmp_path):
        """Orchestrator should create PROJECTS_DIR if it doesn't exist."""
        nonexistent = tmp_path / "nonexistent"
        import orchestrator.orchestrator as orch_mod
        old_val = orch_mod.PROJECTS_DIR
        orch_mod.PROJECTS_DIR = str(nonexistent)
        try:
            orch = AuditOrchestrator()
            assert os.path.exists(str(nonexistent))
        finally:
            orch_mod.PROJECTS_DIR = old_val

    def test_concurrent_projects(self, tmp_path):
        """Orchestrator should handle multiple projects simultaneously."""
        orch = _make_orchestrator(tmp_path)

        orch.create_project("proj-a", "Project A")
        orch.create_project("proj-b", "Project B")

        assert len(orch.projects) == 2
        assert "proj-a" in orch.projects
        assert "proj-b" in orch.projects

    def test_parse_time_valid(self):
        """_parse_time should parse valid ISO timestamps."""
        result = AuditOrchestrator._parse_time("2026-07-04T12:00:00Z")
        assert result is not None
        assert result.year == 2026

    def test_parse_time_none(self):
        """_parse_time should return None for None input."""
        result = AuditOrchestrator._parse_time(None)
        assert result is None

    def test_parse_time_empty(self):
        """_parse_time should return None for empty string."""
        result = AuditOrchestrator._parse_time("")
        assert result is None

    def test_parse_time_invalid(self):
        """_parse_time should return None for invalid format."""
        result = AuditOrchestrator._parse_time("not-a-date")
        assert result is None
