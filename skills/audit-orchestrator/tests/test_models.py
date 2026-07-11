"""
Comprehensive tests for Audit Orchestrator — Phase 1: State Machine Core

Covers:
- Phase advancement follows PHASE_ORDER correctly
- Invalid transitions raise errors
- get_next_agent() returns correct agent per phase
- get_dispatch_prompt() includes all required variables
- trash() sets trashed_at timestamp
- cancel() sets cancelled_at + reason
- restore() clears timestamps and selects correct phase
- days_until_removal() counts down
- Serialization round-trip (to_dict → from_dict)
- atomic_write creates file and is atomic
- File lock context manager works
"""

import os
import json
import time
import tempfile
import datetime

import pytest

from orchestrator.models import (
    AuditPhase,
    AuditProject,
    PHASE_ORDER,
    atomic_write,
    file_lock,
)
from orchestrator.config import (
    PHASE_OWNERS,
    PHASE_ARTIFACTS,
    PHASE_TIMEOUTS,
    PHASE_PLAN_FILES,
    PHASE_OUTPUT_FILES,
    PHASE_STATUS_FILES,
    AGENT_MODELS,
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


# ══════════════════════════════════════════════════════════════════════
# AuditPhase Enum Tests
# ══════════════════════════════════════════════════════════════════════

class TestAuditPhase:
    def test_all_phases_exist(self):
        expected = {
            "PLANNING", "READY_FOR_AUDIT",
            "R1_ECHO", "R1_TRIPP", "R1_CONSOLIDATE",
            "R2_ECHO", "R2_TRIPP", "R2_CONSOLIDATE",
            "READY_FOR_BUILD", "BUILDING",
            "STORED", "TRASHED", "CANCELLED",
        }
        actual = {p.value for p in AuditPhase}
        assert actual == expected

    def test_phase_count(self):
        assert len(AuditPhase) == 13

    def test_phase_order_has_10_entries(self):
        """PHASE_ORDER covers the sequential advance path (10 phases)."""
        assert len(PHASE_ORDER) == 10

    def test_terminal_phases_not_in_order(self):
        """STORED, TRASHED, CANCELLED are not in PHASE_ORDER (reached via actions)."""
        order_values = {p.value for p in PHASE_ORDER}
        assert "STORED" not in order_values
        assert "TRASHED" not in order_values
        assert "CANCELLED" not in order_values


# ══════════════════════════════════════════════════════════════════════
# Phase Advancement Tests
# ══════════════════════════════════════════════════════════════════════

class TestPhaseAdvancement:
    def test_full_journey(self):
        """Advance through every phase in PHASE_ORDER."""
        p = _make_project()
        for expected_phase in PHASE_ORDER:
            assert p.phase == expected_phase.value
            if p.phase != AuditPhase.BUILDING.value:
                p.advance()
        # After BUILDING, cannot advance further
        assert p.phase == AuditPhase.BUILDING.value

    def test_cannot_advance_from_building(self):
        p = _make_project(phase="BUILDING")
        with pytest.raises(ValueError, match="terminal phase"):
            p.advance()

    def test_cannot_advance_from_stored(self):
        """STORED is not in PHASE_ORDER, so index() raises ValueError."""
        p = _make_project(phase="STORED")
        with pytest.raises(ValueError):
            p.advance()

    def test_cannot_advance_from_trashed(self):
        p = _make_project(phase="TRASHED")
        with pytest.raises(ValueError):
            p.advance()

    def test_cannot_advance_from_cancelled(self):
        p = _make_project(phase="CANCELLED")
        with pytest.raises(ValueError):
            p.advance()

    def test_advance_updates_phase_started_at(self):
        p = _make_project()
        old_time = p.phase_started_at
        time.sleep(0.01)
        p.advance()
        assert p.phase_started_at != old_time

    def test_advance_updates_timeout(self):
        """Timeout should update when entering a phase with a configured timeout."""
        p = _make_project(phase="READY_FOR_AUDIT")
        assert p.timeout_minutes is None
        p.advance()  # → R1_ECHO (timeout=120)
        assert p.timeout_minutes == 120

    def test_advance_resets_error_tracking(self):
        p = _make_project()
        p.error_tracking["consecutive_errors"] = 5
        p.error_tracking["alert_suppressed"] = True
        p.advance()
        assert p.error_tracking["consecutive_errors"] == 0
        assert p.error_tracking["alert_suppressed"] is False

    def test_round_increments_at_r2_boundary(self):
        """Round should become 2 when crossing from R1_CONSOLIDATE to R2_ECHO."""
        p = _make_project(phase="R1_CONSOLIDATE", round=1)
        assert p.round == 1
        p.advance()  # → R2_ECHO
        assert p.phase == "R2_ECHO"
        assert p.round == 2

    def test_round_stays_1_through_r1(self):
        p = _make_project()
        p.advance()  # READY_FOR_AUDIT
        p.advance()  # R1_ECHO
        assert p.round == 1
        p.advance()  # R1_TRIPP
        assert p.round == 1
        p.advance()  # R1_CONSOLIDATE
        assert p.round == 1

    def test_round_stays_2_through_r2(self):
        p = _make_project(phase="R2_ECHO", round=2)
        p.advance()  # R2_TRIPP
        assert p.round == 2
        p.advance()  # R2_CONSOLIDATE
        assert p.round == 2


# ══════════════════════════════════════════════════════════════════════
# get_next_agent() Tests
# ══════════════════════════════════════════════════════════════════════

class TestGetNextAgent:
    def test_all_dispatch_phases(self):
        expected = {
            "PLANNING":          "cyony",
            "READY_FOR_AUDIT":   "orchestrator",
            "R1_ECHO":           "echo",
            "R1_TRIPP":          "tripp",
            "R1_CONSOLIDATE":    "cyony",
            "R2_ECHO":           "echo",
            "R2_TRIPP":          "tripp",
            "R2_CONSOLIDATE":    "cyony",
            "READY_FOR_BUILD":   "orchestrator",
            "BUILDING":          "codex",
        }
        for phase_name, expected_agent in expected.items():
            p = _make_project(phase=phase_name)
            assert p.get_next_agent() == expected_agent, (
                f"Phase {phase_name} should be owned by {expected_agent}"
            )


# ══════════════════════════════════════════════════════════════════════
# get_dispatch_prompt() Tests
# ══════════════════════════════════════════════════════════════════════

class TestGetDispatchPrompt:
    def test_r1_echo_prompt(self):
        p = _make_project(phase="R1_ECHO", round=1)
        prompt = p.get_dispatch_prompt(project_path="/tmp/proj")

        assert "You are echo" in prompt
        assert "auditing a project plan" in prompt
        assert "PROJECT: Test Project" in prompt
        assert "YOUR PHASE: R1_ECHO (Round 1)" in prompt
        assert "PLAN TO AUDIT: /tmp/proj/LEAD_PLAN.md" in prompt
        assert "ECHO_AUDIT_R1.md" in prompt
        assert ".status/echo_r1.json" in prompt
        assert "Do NOT use delegate_task" in prompt
        assert "Do NOT spawn subagents" in prompt
        assert "AUDIT_META" in prompt

    def test_r1_tripp_independent(self):
        """R1 Tripp should NOT reference Echo's audit (independent)."""
        p = _make_project(phase="R1_TRIPP", round=1)
        prompt = p.get_dispatch_prompt(project_path="/tmp/proj")
        assert "TRIPP_AUDIT_R1.md" in prompt
        # Should not reference ECHO_AUDIT_R1.md as a conditional ref
        assert "ECHO_AUDIT_R1.md" not in prompt

    def test_r2_tripp_references_echo(self):
        """R2 Tripp should reference Echo's R2 audit."""
        p = _make_project(phase="R2_TRIPP", round=2)
        prompt = p.get_dispatch_prompt(project_path="/tmp/proj")
        assert "ECHO_AUDIT_R2.md" in prompt
        assert "Round 1 audits for context" in prompt

    def test_consolidation_prompt(self):
        """Consolidation phases should say 'consolidating audit findings'."""
        p = _make_project(phase="R1_CONSOLIDATE", round=1)
        prompt = p.get_dispatch_prompt(project_path="/tmp/proj")
        assert "consolidating audit findings" in prompt
        assert "ECHO_AUDIT_R1.md" in prompt
        assert "TRIPP_AUDIT_R1.md" in prompt

    def test_r2_consolidation_prompt(self):
        p = _make_project(phase="R2_CONSOLIDATE", round=2)
        prompt = p.get_dispatch_prompt(project_path="/tmp/proj")
        assert "consolidating audit findings" in prompt
        assert "ECHO_AUDIT_R2.md" in prompt
        assert "TRIPP_AUDIT_R2.md" in prompt

    def test_non_dispatch_phase_raises(self):
        """Phases without plan/output/status mappings should raise."""
        p = _make_project(phase="PLANNING")
        with pytest.raises(ValueError, match="not an agent-dispatch phase"):
            p.get_dispatch_prompt()

    def test_ready_for_build_raises(self):
        p = _make_project(phase="READY_FOR_BUILD")
        with pytest.raises(ValueError, match="not an agent-dispatch phase"):
            p.get_dispatch_prompt()

    def test_prompt_includes_scope_boundary(self):
        p = _make_project(phase="R1_ECHO")
        prompt = p.get_dispatch_prompt(project_path="/opt/data/shared/audit-workflow/test")
        assert "Only read files within this directory" in prompt
        assert "Do NOT read files outside" in prompt
        assert "Do NOT modify any files except" in prompt

    def test_prompt_uses_project_id_in_path(self):
        """Default project_path should use PROJECTS_DIR + project_id."""
        p = _make_project(project_id="my-project", phase="R1_ECHO")
        prompt = p.get_dispatch_prompt()
        assert "/opt/data/shared/audit-workflow/my-project" in prompt


# ══════════════════════════════════════════════════════════════════════
# trash() Tests
# ══════════════════════════════════════════════════════════════════════

class TestTrash:
    def test_trash_sets_phase(self):
        p = _make_project()
        p.trash()
        assert p.phase == "TRASHED"

    def test_trash_sets_trashed_at(self):
        p = _make_project()
        assert p.trashed_at is None
        p.trash()
        assert p.trashed_at is not None
        assert "T" in p.trashed_at  # ISO format check

    def test_trash_updates_timestamp(self):
        p = _make_project()
        old = p.updated_at
        time.sleep(0.01)
        p.trash()
        assert p.updated_at != old


# ══════════════════════════════════════════════════════════════════════
# cancel() Tests
# ══════════════════════════════════════════════════════════════════════

class TestCancel:
    def test_cancel_sets_phase(self):
        p = _make_project()
        p.cancel("No longer needed")
        assert p.phase == "CANCELLED"

    def test_cancel_sets_cancelled_at(self):
        p = _make_project()
        assert p.cancelled_at is None
        p.cancel("Changed direction")
        assert p.cancelled_at is not None

    def test_cancel_sets_reason(self):
        p = _make_project()
        p.cancel("Plan is obsolete")
        assert p.cancel_reason == "Plan is obsolete"

    def test_cancel_requires_reason(self):
        """cancel() should accept any string, even empty."""
        p = _make_project()
        p.cancel("")
        assert p.cancel_reason == ""


# ══════════════════════════════════════════════════════════════════════
# restore() Tests
# ══════════════════════════════════════════════════════════════════════

class TestRestore:
    def test_restore_from_trashed_clears_trashed_at(self):
        p = _make_project()
        p.trash()
        assert p.trashed_at is not None
        p.restore()
        assert p.trashed_at is None

    def test_restore_from_cancelled_clears_all(self):
        p = _make_project()
        p.cancel("reason")
        p.restore()
        assert p.cancelled_at is None
        assert p.cancel_reason is None

    def test_restore_without_artifacts_goes_to_planning(self):
        p = _make_project(phase="TRASHED")
        p.trash()
        p.restore()
        assert p.phase == "PLANNING"

    def test_restore_with_final_artifact_goes_to_ready(self):
        p = _make_project(phase="TRASHED")
        p.trash()
        p.artifacts["final"] = "FINAL_PLAN.md"
        p.restore()
        assert p.phase == "READY_FOR_BUILD"

    def test_restore_updates_timestamp(self):
        p = _make_project()
        p.trash()
        old = p.updated_at
        time.sleep(0.01)
        p.restore()
        assert p.updated_at != old


# ══════════════════════════════════════════════════════════════════════
# days_until_removal() Tests
# ══════════════════════════════════════════════════════════════════════

class TestDaysUntilRemoval:
    def test_not_trashed_returns_zero(self):
        p = _make_project()
        assert p.days_until_removal() == 0

    def test_just_trashed_returns_20(self):
        p = _make_project()
        p.trash()
        assert p.days_until_removal() == 20

    def test_trashed_10_days_ago_returns_10(self):
        p = _make_project()
        # Set trashed_at to 10 days ago
        ten_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=10)
        p.trashed_at = ten_days_ago.isoformat() + "Z"
        assert p.days_until_removal() == 10

    def test_expired_returns_zero(self):
        p = _make_project()
        twenty_one_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=21)
        p.trashed_at = twenty_one_days_ago.isoformat() + "Z"
        assert p.days_until_removal() == 0

    def test_trash_warning_threshold(self):
        """At 13 days, should show 7 days remaining."""
        p = _make_project()
        thirteen_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=13)
        p.trashed_at = thirteen_days_ago.isoformat() + "Z"
        assert p.days_until_removal() == 7


# ══════════════════════════════════════════════════════════════════════
# Serialization Round-Trip Tests
# ══════════════════════════════════════════════════════════════════════

class TestSerialization:
    def test_round_trip_preserves_all_fields(self):
        p = _make_project(
            project_id="trip-mind",
            name="Tripp.Mind Features",
            lead="Cyony",
            phase="R2_TRIPP",
            round=2,
            timeout_minutes=120,
            model={"provider": "xiaomi", "model": "mimo-v2.5"},
        )
        p.error_tracking["consecutive_errors"] = 2
        p.error_tracking["last_error_at"] = "2026-07-04T20:00:00Z"
        p.artifacts["echo_r1"] = "ECHO_AUDIT_R1.md"
        p.artifacts["tripp_r1"] = "TRIPP_AUDIT_R1.md"

        d = p.to_dict()
        p2 = AuditProject.from_dict(d)

        assert p2.project_id == "trip-mind"
        assert p2.name == "Tripp.Mind Features"
        assert p2.lead == "Cyony"
        assert p2.phase == "R2_TRIPP"
        assert p2.round == 2
        assert p2.timeout_minutes == 120
        assert p2.model == {"provider": "xiaomi", "model": "mimo-v2.5"}
        assert p2.error_tracking["consecutive_errors"] == 2
        assert p2.error_tracking["last_error_at"] == "2026-07-04T20:00:00Z"
        assert p2.artifacts["echo_r1"] == "ECHO_AUDIT_R1.md"
        assert p2.artifacts["tripp_r1"] == "TRIPP_AUDIT_R1.md"
        assert p2.trashed_at is None
        assert p2.cancelled_at is None
        assert p2.cancel_reason is None

    def test_round_trip_with_trashed(self):
        p = _make_project()
        p.trash()
        d = p.to_dict()
        p2 = AuditProject.from_dict(d)
        assert p2.phase == "TRASHED"
        assert p2.trashed_at is not None

    def test_round_trip_with_cancelled(self):
        p = _make_project()
        p.cancel("Done with this")
        d = p.to_dict()
        p2 = AuditProject.from_dict(d)
        assert p2.phase == "CANCELLED"
        assert p2.cancelled_at is not None
        assert p2.cancel_reason == "Done with this"

    def test_to_dict_matches_v3_format(self):
        """Output dict should match the v3 state file schema."""
        p = _make_project(project_id="x", name="X")
        d = p.to_dict()
        required_keys = {
            "project_id", "name", "lead", "phase", "round",
            "created_at", "updated_at", "phase_started_at",
            "timeout_minutes", "model",
            "trashed_at", "cancelled_at", "cancel_reason",
            "error_tracking", "artifacts",
        }
        assert required_keys.issubset(d.keys())

    def test_from_dict_minimal(self):
        """from_dict should work with only required fields."""
        data = {"project_id": "minimal", "name": "Minimal"}
        p = AuditProject.from_dict(data)
        assert p.project_id == "minimal"
        assert p.phase == "PLANNING"
        assert p.round == 1
        assert p.lead == "Cyony"

    def test_json_serializable(self):
        """to_dict output should be JSON-serializable."""
        p = _make_project()
        d = p.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)
        # And should round-trip through JSON
        d2 = json.loads(serialized)
        assert d2["project_id"] == p.project_id


# ══════════════════════════════════════════════════════════════════════
# atomic_write() Tests
# ══════════════════════════════════════════════════════════════════════

class TestAtomicWrite:
    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.txt")
            atomic_write(path, "hello world")
            assert os.path.exists(path)
            with open(path) as f:
                assert f.read() == "hello world"

    def test_overwrites_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.txt")
            atomic_write(path, "first")
            atomic_write(path, "second")
            with open(path) as f:
                assert f.read() == "second"

    def test_no_tmp_file_left_after_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.txt")
            atomic_write(path, "content")
            assert not os.path.exists(path + ".tmp")

    def test_creates_parent_dirs_if_needed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "dir", "file.txt")
            atomic_write(path, "nested")
            assert os.path.exists(path)
            with open(path) as f:
                assert f.read() == "nested"

    def test_content_is_flushed(self):
        """After atomic_write, reading the file should get the full content."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "big.txt")
            content = "x" * 100000
            atomic_write(path, content)
            with open(path) as f:
                assert len(f.read()) == 100000


# ══════════════════════════════════════════════════════════════════════
# file_lock() Tests
# ══════════════════════════════════════════════════════════════════════

class TestFileLock:
    def test_creates_lock_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "state.json")
            with file_lock(target):
                assert os.path.exists(target + ".lock")

    def test_lock_releases_after_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "state.json")
            with file_lock(target):
                pass
            # Lock file should still exist (sidecar), but not be held
            assert os.path.exists(target + ".lock")

    def test_sequential_locks_work(self):
        """Two sequential lock acquisitions on the same file should both succeed."""
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "state.json")
            with file_lock(target):
                atomic_write(target, '{"round": 1}')
            with file_lock(target):
                atomic_write(target, '{"round": 2}')
            with open(target) as f:
                assert f.read() == '{"round": 2}'

    def test_lock_with_atomic_write(self):
        """Typical usage pattern: lock → write → unlock."""
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "state.json")
            with file_lock(target):
                atomic_write(target, '{"phase": "PLANNING"}')
            with open(target) as f:
                assert f.read() == '{"phase": "PLANNING"}'


# ══════════════════════════════════════════════════════════════════════
# Config Consistency Tests
# ══════════════════════════════════════════════════════════════════════

class TestConfig:
    def test_phase_owners_cover_all_order_phases(self):
        for phase in PHASE_ORDER:
            assert phase.value in PHASE_OWNERS, (
                f"Phase {phase.value} missing from PHASE_OWNERS"
            )

    def test_phase_artifacts_cover_all_order_phases(self):
        for phase in PHASE_ORDER:
            assert phase.value in PHASE_ARTIFACTS, (
                f"Phase {phase.value} missing from PHASE_ARTIFACTS"
            )

    def test_phase_timeouts_cover_all_order_phases(self):
        for phase in PHASE_ORDER:
            assert phase.value in PHASE_TIMEOUTS, (
                f"Phase {phase.value} missing from PHASE_TIMEOUTS"
            )

    def test_audit_phases_have_120min_timeout(self):
        for phase_name in ["R1_ECHO", "R1_TRIPP", "R2_ECHO", "R2_TRIPP"]:
            assert PHASE_TIMEOUTS[phase_name] == 120

    def test_consolidation_phases_have_30min_timeout(self):
        for phase_name in ["R1_CONSOLIDATE", "R2_CONSOLIDATE"]:
            assert PHASE_TIMEOUTS[phase_name] == 30

    def test_agent_models_have_required_keys(self):
        for agent, model_info in AGENT_MODELS.items():
            assert "provider" in model_info, f"Agent {agent} missing provider"
            assert "model" in model_info, f"Agent {agent} missing model"

    def test_dispatch_phase_mappings_consistent(self):
        """Every dispatch phase should have plan, output, and status files."""
        dispatch_phases = [
            "R1_ECHO", "R1_TRIPP", "R1_CONSOLIDATE",
            "R2_ECHO", "R2_TRIPP", "R2_CONSOLIDATE",
        ]
        for phase_name in dispatch_phases:
            assert phase_name in PHASE_PLAN_FILES, f"{phase_name} missing plan"
            assert phase_name in PHASE_OUTPUT_FILES, f"{phase_name} missing output"
            assert phase_name in PHASE_STATUS_FILES, f"{phase_name} missing status"
