"""
Comprehensive tests for Audit Orchestrator — Phase 6: Action Handlers

Covers:
- action_yes sets phase to BUILDING
- action_store sets phase to STORED
- action_trash sets phase to TRASHED and trashed_at
- action_cancel sets phase, reason, moves directory
- action_cancel rejects empty reason
- action_restore from STORED works
- action_restore from TRASHED works (clears trashed_at)
- action_restore from CANCELLED works (moves dir back)
- action_restore rejects non-restorable phase
- action_extend_timeout adds time and resets clock
- cleanup_expired_trash deletes old projects
- cleanup_expired_trash keeps recent projects
"""

import os
import json
import time
import datetime
from unittest.mock import patch, MagicMock

import pytest

from orchestrator.models import AuditProject, AuditPhase, atomic_write
from orchestrator.actions import (
    action_yes,
    action_store,
    action_trash,
    action_cancel,
    action_restore,
    action_extend_timeout,
    cleanup_expired_trash,
)


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


def _create_project_dir(tmp_path, project_id="test-project"):
    """Create a project directory with a project_state.json."""
    project_dir = tmp_path / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def _make_orchestrator_mock(tmp_path):
    """Create a mock orchestrator that saves to tmp_path."""
    mock = MagicMock()
    mock.projects = {}

    def save_project(project_id):
        project = mock.projects.get(project_id)
        if project is None:
            return
        project_dir = tmp_path / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        state_path = project_dir / "project_state.json"
        atomic_write(str(state_path), json.dumps(project.to_dict(), indent=2))

    mock.save_project.side_effect = save_project
    return mock


# ══════════════════════════════════════════════════════════════════════
# action_yes Tests
# ══════════════════════════════════════════════════════════════════════


class TestActionYes:
    def test_sets_phase_to_building(self, tmp_path):
        """action_yes should set project phase to BUILDING."""
        project = _make_project()
        orchestrator = _make_orchestrator_mock(tmp_path)
        orchestrator.projects[project.project_id] = project

        with patch("orchestrator.actions.print"):
            result = action_yes(project, orchestrator)

        assert result is True
        assert project.phase == AuditPhase.BUILDING.value

    def test_returns_true(self, tmp_path):
        """action_yes should always return True."""
        project = _make_project()
        orchestrator = _make_orchestrator_mock(tmp_path)
        orchestrator.projects[project.project_id] = project

        with patch("orchestrator.actions.print"):
            result = action_yes(project, orchestrator)

        assert result is True

    def test_saves_state(self, tmp_path):
        """action_yes should save project state to disk."""
        project = _make_project()
        orchestrator = _make_orchestrator_mock(tmp_path)
        orchestrator.projects[project.project_id] = project

        with patch("orchestrator.actions.print"):
            action_yes(project, orchestrator)

        state_path = tmp_path / "test-project" / "project_state.json"
        assert state_path.exists()
        with open(state_path) as f:
            data = json.load(f)
        assert data["phase"] == "BUILDING"

    def test_sends_notification(self, tmp_path):
        """action_yes should print a notification message."""
        project = _make_project(name="My App")
        orchestrator = _make_orchestrator_mock(tmp_path)
        orchestrator.projects[project.project_id] = project

        with patch("orchestrator.actions.print") as mock_print:
            action_yes(project, orchestrator)

        mock_print.assert_called_once()
        msg = mock_print.call_args[0][0]
        assert "✅" in msg
        assert "Build started" in msg
        assert "My App" in msg


# ══════════════════════════════════════════════════════════════════════
# action_store Tests
# ══════════════════════════════════════════════════════════════════════


class TestActionStore:
    def test_sets_phase_to_stored(self, tmp_path):
        """action_store should set project phase to STORED."""
        project = _make_project()

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            result = action_store(project)

        assert result is True
        assert project.phase == AuditPhase.STORED.value

    def test_returns_true(self, tmp_path):
        """action_store should always return True."""
        project = _make_project()

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            result = action_store(project)

        assert result is True

    def test_sends_notification(self, tmp_path):
        """action_store should print a notification."""
        project = _make_project(name="Stored App")

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print") as mock_print:
            action_store(project)

        msg = mock_print.call_args[0][0]
        assert "📁" in msg
        assert "Stored App" in msg
        assert "stored" in msg
        assert "Restore" in msg


# ══════════════════════════════════════════════════════════════════════
# action_trash Tests
# ══════════════════════════════════════════════════════════════════════


class TestActionTrash:
    def test_sets_phase_to_trashed(self, tmp_path):
        """action_trash should set project phase to TRASHED."""
        project = _make_project()

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            result = action_trash(project)

        assert result is True
        assert project.phase == AuditPhase.TRASHED.value

    def test_sets_trashed_at(self, tmp_path):
        """action_trash should set trashed_at timestamp."""
        project = _make_project()
        assert project.trashed_at is None

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            action_trash(project)

        assert project.trashed_at is not None
        assert "T" in project.trashed_at  # ISO format check

    def test_returns_true(self, tmp_path):
        """action_trash should always return True."""
        project = _make_project()

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            result = action_trash(project)

        assert result is True

    def test_sends_notification_with_rescue(self, tmp_path):
        """action_trash should print notification with [Rescue] action."""
        project = _make_project(name="Trashed App")

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print") as mock_print:
            action_trash(project)

        msg = mock_print.call_args[0][0]
        assert "🗑️" in msg
        assert "Trashed App" in msg
        assert "trashed" in msg
        assert "20 days" in msg
        assert "[Rescue]" in msg


# ══════════════════════════════════════════════════════════════════════
# action_cancel Tests
# ══════════════════════════════════════════════════════════════════════


class TestActionCancel:
    def test_sets_phase_to_cancelled(self, tmp_path):
        """action_cancel should set project phase to CANCELLED."""
        project = _make_project()
        _create_project_dir(tmp_path)

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            result = action_cancel(project, "No longer needed")

        assert result is True
        assert project.phase == AuditPhase.CANCELLED.value

    def test_sets_cancel_reason(self, tmp_path):
        """action_cancel should set cancel_reason."""
        project = _make_project()
        _create_project_dir(tmp_path)

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            action_cancel(project, "Plan is obsolete")

        assert project.cancel_reason == "Plan is obsolete"

    def test_moves_directory(self, tmp_path):
        """action_cancel should move project dir to .cancelled/ suffix."""
        project = _make_project()
        project_dir = _create_project_dir(tmp_path)
        # Create a file in the project dir
        (project_dir / "LEAD_PLAN.md").write_text("# Plan")

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            action_cancel(project, "Changed direction")

        # Original dir should not exist
        assert not project_dir.exists()
        # Cancelled dir should exist
        cancelled_dir = tmp_path / "test-project.cancelled"
        assert cancelled_dir.exists()
        assert (cancelled_dir / "LEAD_PLAN.md").exists()

    def test_creates_cancelled_metadata(self, tmp_path):
        """action_cancel should create cancelled.json metadata file."""
        project = _make_project(project_id="proj-1", name="My Project")
        _create_project_dir(tmp_path, "proj-1")

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            action_cancel(project, "Budget cuts")

        cancelled_dir = tmp_path / "proj-1.cancelled"
        metadata_path = cancelled_dir / "cancelled.json"
        assert metadata_path.exists()

        with open(metadata_path) as f:
            metadata = json.load(f)
        assert metadata["reason"] == "Budget cuts"
        assert metadata["project_id"] == "proj-1"
        assert metadata["name"] == "My Project"
        assert "cancelled_at" in metadata

    def test_rejects_empty_reason(self, tmp_path):
        """action_cancel should raise ValueError for empty reason."""
        project = _make_project()

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            with pytest.raises(ValueError, match="non-empty"):
                action_cancel(project, "")

    def test_rejects_whitespace_only_reason(self, tmp_path):
        """action_cancel should raise ValueError for whitespace-only reason."""
        project = _make_project()

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            with pytest.raises(ValueError, match="non-empty"):
                action_cancel(project, "   ")

    def test_sends_notification(self, tmp_path):
        """action_cancel should print notification with reason."""
        project = _make_project(name="Cancelled App")
        _create_project_dir(tmp_path)

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print") as mock_print:
            action_cancel(project, "Too expensive")

        msg = mock_print.call_args[0][0]
        assert "❌" in msg
        assert "Cancelled App" in msg
        assert "cancelled" in msg
        assert "Too expensive" in msg


# ══════════════════════════════════════════════════════════════════════
# action_restore Tests
# ══════════════════════════════════════════════════════════════════════


class TestActionRestore:
    def test_restore_from_stored(self, tmp_path):
        """action_restore from STORED should restore to PLANNING."""
        project = _make_project(phase="STORED")

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            result = action_restore(project)

        assert result is True
        # No final artifact → restored to PLANNING
        assert project.phase == AuditPhase.PLANNING.value

    def test_restore_from_trashed(self, tmp_path):
        """action_restore from TRASHED should clear trashed_at."""
        project = _make_project(phase="TRASHED")
        project.trashed_at = datetime.datetime.utcnow().isoformat() + "Z"
        assert project.trashed_at is not None

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            action_restore(project)

        assert project.trashed_at is None

    def test_restore_from_trashed_with_final_artifact(self, tmp_path):
        """action_restore from TRASHED with final artifact → READY_FOR_BUILD."""
        project = _make_project(phase="TRASHED")
        project.trashed_at = datetime.datetime.utcnow().isoformat() + "Z"
        project.artifacts["final"] = "FINAL_PLAN.md"

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            action_restore(project)

        assert project.phase == AuditPhase.READY_FOR_BUILD.value

    def test_restore_from_cancelled_moves_dir_back(self, tmp_path):
        """action_restore from CANCELLED should move directory back."""
        project = _make_project(project_id="proj-cancel", phase="CANCELLED")
        project.cancelled_at = datetime.datetime.utcnow().isoformat() + "Z"
        project.cancel_reason = "reason"

        # Create the .cancelled directory
        cancelled_dir = tmp_path / "proj-cancel.cancelled"
        cancelled_dir.mkdir(parents=True)
        (cancelled_dir / "LEAD_PLAN.md").write_text("# Plan")

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            action_restore(project)

        # Original dir should now exist
        original_dir = tmp_path / "proj-cancel"
        assert original_dir.exists()
        assert (original_dir / "LEAD_PLAN.md").exists()

        # .cancelled dir should not exist
        assert not cancelled_dir.exists()

    def test_restore_from_cancelled_clears_timestamps(self, tmp_path):
        """action_restore from CANCELLED should clear cancelled_at."""
        project = _make_project(phase="CANCELLED")
        project.cancelled_at = datetime.datetime.utcnow().isoformat() + "Z"
        project.cancel_reason = "reason"

        cancelled_dir = tmp_path / "test-project.cancelled"
        cancelled_dir.mkdir(parents=True)

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            action_restore(project)

        assert project.cancelled_at is None
        assert project.cancel_reason is None

    def test_rejects_non_restorable_phase(self, tmp_path):
        """action_restore should raise ValueError for non-restorable phases."""
        for phase in ["PLANNING", "READY_FOR_AUDIT", "R1_ECHO",
                       "BUILDING"]:
            project = _make_project(phase=phase)

            with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
                 patch("orchestrator.actions.print"):
                with pytest.raises(ValueError, match="Cannot restore"):
                    action_restore(project)

    def test_sends_notification(self, tmp_path):
        """action_restore should print a notification."""
        project = _make_project(name="Restored App", phase="STORED")

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print") as mock_print:
            action_restore(project)

        msg = mock_print.call_args[0][0]
        assert "🔄" in msg
        assert "Restored App" in msg
        assert "restored" in msg


# ══════════════════════════════════════════════════════════════════════
# action_extend_timeout Tests
# ══════════════════════════════════════════════════════════════════════


class TestActionExtendTimeout:
    def test_adds_time(self, tmp_path):
        """action_extend_timeout should add minutes to timeout_minutes."""
        project = _make_project(timeout_minutes=60)

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            result = action_extend_timeout(project, minutes=30)

        assert result is True
        assert project.timeout_minutes == 90

    def test_defaults_to_30_minutes(self, tmp_path):
        """action_extend_timeout should default to 30 minutes."""
        project = _make_project(timeout_minutes=60)

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            action_extend_timeout(project)

        assert project.timeout_minutes == 90

    def test_resets_clock(self, tmp_path):
        """action_extend_timeout should update phase_started_at to now."""
        project = _make_project()
        old_time = project.phase_started_at
        time.sleep(0.01)

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            action_extend_timeout(project)

        assert project.phase_started_at != old_time

    def test_handles_none_timeout(self, tmp_path):
        """action_extend_timeout should handle None timeout_minutes."""
        project = _make_project(timeout_minutes=None)

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print"):
            action_extend_timeout(project, minutes=30)

        assert project.timeout_minutes == 30

    def test_sends_notification(self, tmp_path):
        """action_extend_timeout should print notification."""
        project = _make_project(name="Timed App")

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)), \
             patch("orchestrator.actions.print") as mock_print:
            action_extend_timeout(project, minutes=45)

        msg = mock_print.call_args[0][0]
        assert "⏰" in msg
        assert "+45min" in msg
        assert "Timed App" in msg


# ══════════════════════════════════════════════════════════════════════
# cleanup_expired_trash Tests
# ══════════════════════════════════════════════════════════════════════


class TestCleanupExpiredTrash:
    def test_deletes_old_projects(self, tmp_path):
        """cleanup_expired_trash should delete projects trashed >20 days ago."""
        project = _make_project(project_id="old-project")
        project.trash()
        # Set trashed_at to 21 days ago
        twenty_one_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=21)
        project.trashed_at = twenty_one_days_ago.isoformat() + "Z"

        # Create project directory
        project_dir = tmp_path / "old-project"
        project_dir.mkdir(parents=True)
        (project_dir / "file.txt").write_text("content")

        projects_dict = {"old-project": project}

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)):
            deleted = cleanup_expired_trash(projects_dict)

        assert "old-project" in deleted
        assert "old-project" not in projects_dict
        assert not project_dir.exists()

    def test_keeps_recent_projects(self, tmp_path):
        """cleanup_expired_trash should keep projects trashed <20 days ago."""
        project = _make_project(project_id="recent-project")
        project.trash()
        # Set trashed_at to 5 days ago
        five_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=5)
        project.trashed_at = five_days_ago.isoformat() + "Z"

        # Create project directory
        project_dir = tmp_path / "recent-project"
        project_dir.mkdir(parents=True)

        projects_dict = {"recent-project": project}

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)):
            deleted = cleanup_expired_trash(projects_dict)

        assert deleted == []
        assert "recent-project" in projects_dict
        assert project_dir.exists()

    def test_skips_non_trashed_projects(self, tmp_path):
        """cleanup_expired_trash should skip projects not in TRASHED phase."""
        project = _make_project(project_id="active-project", phase="PLANNING")

        projects_dict = {"active-project": project}

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)):
            deleted = cleanup_expired_trash(projects_dict)

        assert deleted == []
        assert "active-project" in projects_dict

    def test_returns_deleted_ids(self, tmp_path):
        """cleanup_expired_trash should return list of deleted project IDs."""
        # Create two expired projects
        expired1 = _make_project(project_id="expired-1")
        expired1.trash()
        expired1.trashed_at = (datetime.datetime.utcnow() - datetime.timedelta(days=25)).isoformat() + "Z"

        expired2 = _make_project(project_id="expired-2")
        expired2.trash()
        expired2.trashed_at = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).isoformat() + "Z"

        # Create directories
        (tmp_path / "expired-1").mkdir(parents=True)
        (tmp_path / "expired-2").mkdir(parents=True)

        projects_dict = {
            "expired-1": expired1,
            "expired-2": expired2,
        }

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)):
            deleted = cleanup_expired_trash(projects_dict)

        assert sorted(deleted) == ["expired-1", "expired-2"]
        assert len(projects_dict) == 0

    def test_mixed_expired_and_recent(self, tmp_path):
        """cleanup_expired_trash handles mix of expired and recent."""
        expired = _make_project(project_id="expired")
        expired.trash()
        expired.trashed_at = (datetime.datetime.utcnow() - datetime.timedelta(days=22)).isoformat() + "Z"

        recent = _make_project(project_id="recent")
        recent.trash()
        recent.trashed_at = (datetime.datetime.utcnow() - datetime.timedelta(days=3)).isoformat() + "Z"

        (tmp_path / "expired").mkdir(parents=True)
        (tmp_path / "recent").mkdir(parents=True)

        projects_dict = {
            "expired": expired,
            "recent": recent,
        }

        with patch("orchestrator.actions.PROJECTS_DIR", str(tmp_path)):
            deleted = cleanup_expired_trash(projects_dict)

        assert deleted == ["expired"]
        assert "recent" in projects_dict
        assert "expired" not in projects_dict
