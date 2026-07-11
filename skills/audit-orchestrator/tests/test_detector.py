"""
Comprehensive tests for Audit Orchestrator — Phase 2: Completion Detection + Error Handling

Covers:
- Completion detection (status file exists/missing)
- Malformed JSON handling
- Error counter increments correctly
- Alert suppression activates at MAX_ALERTSUPPRESSION (3)
- Error reset on phase advance
- Artifact validation (empty, small, good files)
- Score validation (both low, wide gap, normal)
"""

import os
import json
import time
import tempfile

import pytest

from orchestrator.config import (
    PHASE_OUTPUT_FILES,
    PHASE_STATUS_FILES,
    MAX_ALERTSUPPRESSION,
)
from orchestrator.models import AuditProject
from orchestrator.detector import (
    check_completion,
    validate_artifact,
    parse_status,
    validate_status_json,
    record_error,
    reset_errors,
    check_scores,
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
    output_file = PHASE_OUTPUT_FILES[phase]
    artifact_path = os.path.join(project_dir, output_file)
    os.makedirs(os.path.dirname(artifact_path) or ".", exist_ok=True)
    with open(artifact_path, "w") as f:
        f.write(content)
    return artifact_path


# ══════════════════════════════════════════════════════════════════════
# Completion Detection Tests
# ══════════════════════════════════════════════════════════════════════

class TestCheckCompletion:
    def test_returns_true_when_status_file_exists(self, tmp_path):
        """check_completion should return True when status file exists with valid JSON."""
        status_data = {"status": "done", "agent": "echo", "score": 7}
        _write_status_file(str(tmp_path), "R1_ECHO", status_data)

        # Mock time.sleep to avoid 5s wait in tests
        import orchestrator.detector as detector_mod
        original_sleep = time.sleep
        time.sleep = lambda x: None
        try:
            result = check_completion(str(tmp_path), "R1_ECHO")
        finally:
            time.sleep = original_sleep

        assert result is True

    def test_returns_false_when_status_file_missing(self, tmp_path):
        """check_completion should return False when no status file exists."""
        import orchestrator.detector as detector_mod
        original_sleep = time.sleep
        time.sleep = lambda x: None
        try:
            result = check_completion(str(tmp_path), "R1_ECHO")
        finally:
            time.sleep = original_sleep

        assert result is False

    def test_returns_false_for_malformed_json(self, tmp_path):
        """check_completion should return False for malformed JSON."""
        status_file = PHASE_STATUS_FILES["R1_ECHO"]
        status_path = os.path.join(tmp_path, status_file)
        os.makedirs(os.path.dirname(status_path), exist_ok=True)
        with open(status_path, "w") as f:
            f.write("{not valid json!!!")

        import orchestrator.detector as detector_mod
        original_sleep = time.sleep
        time.sleep = lambda x: None
        try:
            result = check_completion(str(tmp_path), "R1_ECHO")
        finally:
            time.sleep = original_sleep

        assert result is False

    def test_returns_false_for_unknown_phase(self, tmp_path):
        """check_completion should return False for phase without status mapping."""
        import orchestrator.detector as detector_mod
        original_sleep = time.sleep
        time.sleep = lambda x: None
        try:
            result = check_completion(str(tmp_path), "NONEXISTENT_PHASE")
        finally:
            time.sleep = original_sleep

        assert result is False

    def test_settling_time_called(self, tmp_path):
        """check_completion should call time.sleep(5) for settling."""
        sleep_calls = []
        original_sleep = time.sleep
        time.sleep = lambda x: sleep_calls.append(x)
        try:
            _write_status_file(str(tmp_path), "R1_ECHO", {"status": "done"})
            check_completion(str(tmp_path), "R1_ECHO")
        finally:
            time.sleep = original_sleep

        assert 5 in sleep_calls


# ══════════════════════════════════════════════════════════════════════
# Artifact Validation Tests
# ══════════════════════════════════════════════════════════════════════

class TestValidateArtifact:
    def test_passes_for_good_file(self, tmp_path):
        """Artifact with >100 chars should be valid."""
        content = "A" * 150
        _write_artifact(str(tmp_path), "R1_ECHO", content)

        is_valid, error = validate_artifact(str(tmp_path), "R1_ECHO")
        assert is_valid is True
        assert error is None

    def test_catches_empty_file(self, tmp_path):
        """Empty artifact file should be invalid."""
        _write_artifact(str(tmp_path), "R1_ECHO", "")

        is_valid, error = validate_artifact(str(tmp_path), "R1_ECHO")
        assert is_valid is False
        assert "empty" in error.lower()

    def test_catches_small_file(self, tmp_path):
        """Artifact with <=100 chars should be invalid."""
        content = "A" * 50
        _write_artifact(str(tmp_path), "R1_ECHO", content)

        is_valid, error = validate_artifact(str(tmp_path), "R1_ECHO")
        assert is_valid is False
        assert "short" in error.lower() or "100" in error

    def test_catches_missing_file(self, tmp_path):
        """Missing artifact file should be invalid."""
        is_valid, error = validate_artifact(str(tmp_path), "R1_ECHO")
        assert is_valid is False
        assert "does not exist" in error.lower() or "not found" in error.lower()

    def test_exactly_101_chars_passes(self, tmp_path):
        """Artifact with exactly 101 chars should pass (101 > 100)."""
        content = "A" * 101
        _write_artifact(str(tmp_path), "R1_ECHO", content)

        is_valid, error = validate_artifact(str(tmp_path), "R1_ECHO")
        assert is_valid is True
        assert error is None

    def test_exactly_100_chars_fails(self, tmp_path):
        """Artifact with exactly 100 chars should fail (not >100)."""
        content = "A" * 100
        _write_artifact(str(tmp_path), "R1_ECHO", content)

        is_valid, error = validate_artifact(str(tmp_path), "R1_ECHO")
        assert is_valid is False

    def test_unknown_phase_returns_error(self, tmp_path):
        """Phase without output mapping should return error."""
        is_valid, error = validate_artifact(str(tmp_path), "PLANNING")
        assert is_valid is False
        assert "no output file" in error.lower() or "configured" in error.lower()


# ══════════════════════════════════════════════════════════════════════
# Status Parsing Tests
# ══════════════════════════════════════════════════════════════════════

class TestParseStatus:
    def test_returns_parsed_dict(self, tmp_path):
        """parse_status should return the parsed JSON dict."""
        status_data = {"status": "done", "agent": "echo", "score": 7}
        _write_status_file(str(tmp_path), "R1_ECHO", status_data)

        result = parse_status(str(tmp_path), "R1_ECHO")
        assert result == status_data

    def test_raises_on_malformed_json(self, tmp_path):
        """parse_status should raise ValueError on malformed JSON."""
        status_file = PHASE_STATUS_FILES["R1_ECHO"]
        status_path = os.path.join(tmp_path, status_file)
        os.makedirs(os.path.dirname(status_path), exist_ok=True)
        with open(status_path, "w") as f:
            f.write("{bad json!!")

        with pytest.raises(ValueError, match="Malformed JSON"):
            parse_status(str(tmp_path), "R1_ECHO")

    def test_raises_on_missing_file(self, tmp_path):
        """parse_status should raise FileNotFoundError for missing status file."""
        with pytest.raises(FileNotFoundError):
            parse_status(str(tmp_path), "R1_ECHO")

    def test_raises_on_unknown_phase(self, tmp_path):
        """parse_status should raise ValueError for phase without status mapping."""
        with pytest.raises(ValueError, match="No status file configured"):
            parse_status(str(tmp_path), "NONEXISTENT")


class TestValidateStatusJson:
    def test_valid_json_returns_tuple(self):
        """validate_status_json should return (dict, None) for valid JSON."""
        raw = '{"status": "done", "score": 7}'
        parsed, error = validate_status_json(raw)
        assert parsed == {"status": "done", "score": 7}
        assert error is None

    def test_malformed_json_returns_error(self):
        """validate_status_json should return (None, error_string) for bad JSON."""
        raw = '{not valid json!!!}'
        parsed, error = validate_status_json(raw)
        assert parsed is None
        assert error is not None
        assert "Malformed JSON" in error

    def test_empty_string_returns_error(self):
        """validate_status_json should handle empty string."""
        parsed, error = validate_status_json("")
        assert parsed is None
        assert error is not None


# ══════════════════════════════════════════════════════════════════════
# Error Tracking Tests
# ══════════════════════════════════════════════════════════════════════

class TestRecordError:
    def test_increments_counter(self):
        """record_error should increment consecutive_errors."""
        project = _make_project()
        assert project.error_tracking["consecutive_errors"] == 0

        record_error(project)
        assert project.error_tracking["consecutive_errors"] == 1

        record_error(project)
        assert project.error_tracking["consecutive_errors"] == 2

    def test_sets_last_error_at(self):
        """record_error should set last_error_at to current time."""
        project = _make_project()
        assert project.error_tracking["last_error_at"] is None

        record_error(project)
        assert project.error_tracking["last_error_at"] is not None
        assert "T" in project.error_tracking["last_error_at"]  # ISO format

    def test_returns_false_below_threshold(self):
        """record_error should return False when below suppression threshold."""
        project = _make_project()
        assert record_error(project) is False  # 1 error
        assert record_error(project) is False  # 2 errors

    def test_suppresses_at_threshold(self):
        """record_error should return True and set alert_suppressed at MAX_ALERTSUPPRESSION."""
        project = _make_project()

        # Record errors up to threshold
        for i in range(MAX_ALERTSUPPRESSION - 1):
            result = record_error(project)
            assert result is False

        # This one should trigger suppression
        result = record_error(project)
        assert result is True
        assert project.error_tracking["alert_suppressed"] is True
        assert project.error_tracking["consecutive_errors"] == MAX_ALERTSUPPRESSION

    def test_stays_suppressed_above_threshold(self):
        """Once suppressed, further errors keep alert_suppressed=True."""
        project = _make_project()

        # Reach threshold
        for _ in range(MAX_ALERTSUPPRESSION):
            record_error(project)

        assert project.error_tracking["alert_suppressed"] is True

        # One more error — still suppressed
        result = record_error(project)
        assert result is True
        assert project.error_tracking["consecutive_errors"] == MAX_ALERTSUPPRESSION + 1


class TestResetErrors:
    def test_resets_counter_to_zero(self):
        """reset_errors should set consecutive_errors to 0."""
        project = _make_project()
        record_error(project)
        record_error(project)
        record_error(project)

        assert project.error_tracking["consecutive_errors"] == 3

        reset_errors(project)
        assert project.error_tracking["consecutive_errors"] == 0

    def test_clears_alert_suppressed(self):
        """reset_errors should set alert_suppressed to False."""
        project = _make_project()
        for _ in range(MAX_ALERTSUPPRESSION):
            record_error(project)

        assert project.error_tracking["alert_suppressed"] is True

        reset_errors(project)
        assert project.error_tracking["alert_suppressed"] is False

    def test_reset_allows_suppression_again(self):
        """After reset, error counter should be able to trigger suppression again."""
        project = _make_project()

        # Reach suppression
        for _ in range(MAX_ALERTSUPPRESSION):
            record_error(project)
        assert project.error_tracking["alert_suppressed"] is True

        # Reset
        reset_errors(project)
        assert project.error_tracking["alert_suppressed"] is False

        # Errors 1 and 2 — not suppressed yet
        assert record_error(project) is False
        assert record_error(project) is False

        # Error 3 — suppressed again
        assert record_error(project) is True


# ══════════════════════════════════════════════════════════════════════
# Score Validation Tests
# ══════════════════════════════════════════════════════════════════════

class TestCheckScores:
    def test_both_low(self, tmp_path):
        """Both R1 scores < 5 should return ('both_low', scores)."""
        _write_status_file(str(tmp_path), "R1_ECHO", {"status": "done", "score": 3})
        _write_status_file(str(tmp_path), "R1_TRIPP", {"status": "done", "score": 4})

        issue, scores = check_scores(str(tmp_path))
        assert issue == "both_low"
        assert scores["echo_r1"] == 3
        assert scores["tripp_r1"] == 4

    def test_wide_gap(self, tmp_path):
        """R1 scores differing by > 4 should return ('wide_gap', scores)."""
        _write_status_file(str(tmp_path), "R1_ECHO", {"status": "done", "score": 2})
        _write_status_file(str(tmp_path), "R1_TRIPP", {"status": "done", "score": 8})

        issue, scores = check_scores(str(tmp_path))
        assert issue == "wide_gap"
        assert scores["echo_r1"] == 2
        assert scores["tripp_r1"] == 8

    def test_normal_scores(self, tmp_path):
        """Normal R1 scores should return (None, scores)."""
        _write_status_file(str(tmp_path), "R1_ECHO", {"status": "done", "score": 7})
        _write_status_file(str(tmp_path), "R1_TRIPP", {"status": "done", "score": 8})

        issue, scores = check_scores(str(tmp_path))
        assert issue is None
        assert scores["echo_r1"] == 7
        assert scores["tripp_r1"] == 8

    def test_exactly_4_gap_is_normal(self, tmp_path):
        """A gap of exactly 4 should not trigger wide_gap."""
        _write_status_file(str(tmp_path), "R1_ECHO", {"status": "done", "score": 3})
        _write_status_file(str(tmp_path), "R1_TRIPP", {"status": "done", "score": 7})

        issue, scores = check_scores(str(tmp_path))
        assert issue is None

    def test_exactly_5_gap_triggers_wide_gap(self, tmp_path):
        """A gap of exactly 5 should trigger wide_gap (> 4)."""
        _write_status_file(str(tmp_path), "R1_ECHO", {"status": "done", "score": 2})
        _write_status_file(str(tmp_path), "R1_TRIPP", {"status": "done", "score": 7})

        issue, scores = check_scores(str(tmp_path))
        assert issue == "wide_gap"

    def test_missing_status_files(self, tmp_path):
        """Missing status files should not crash — returns empty scores."""
        issue, scores = check_scores(str(tmp_path))
        assert issue is None
        assert scores == {}

    def test_one_missing_score(self, tmp_path):
        """If only one score is present, no validation should trigger."""
        _write_status_file(str(tmp_path), "R1_ECHO", {"status": "done", "score": 3})

        issue, scores = check_scores(str(tmp_path))
        assert issue is None
        assert scores["echo_r1"] == 3
        assert "tripp_r1" not in scores

    def test_both_low_at_boundary(self, tmp_path):
        """Both scores at 4 (just below 5) should trigger both_low."""
        _write_status_file(str(tmp_path), "R1_ECHO", {"status": "done", "score": 4})
        _write_status_file(str(tmp_path), "R1_TRIPP", {"status": "done", "score": 4})

        issue, scores = check_scores(str(tmp_path))
        assert issue == "both_low"

    def test_one_low_one_high(self, tmp_path):
        """One low and one high score should not trigger both_low."""
        _write_status_file(str(tmp_path), "R1_ECHO", {"status": "done", "score": 3})
        _write_status_file(str(tmp_path), "R1_TRIPP", {"status": "done", "score": 7})

        issue, scores = check_scores(str(tmp_path))
        assert issue is None


# ══════════════════════════════════════════════════════════════════════
# Integration: Error Reset on Phase Advance
# ══════════════════════════════════════════════════════════════════════

class TestErrorResetOnAdvance:
    def test_advance_resets_error_tracking(self):
        """Phase advance should reset consecutive_errors and alert_suppressed."""
        project = _make_project(phase="R1_ECHO", round=1)

        # Accumulate errors
        for _ in range(MAX_ALERTSUPPRESSION):
            record_error(project)
        assert project.error_tracking["consecutive_errors"] == MAX_ALERTSUPPRESSION
        assert project.error_tracking["alert_suppressed"] is True

        # Advance phase
        project.advance()

        # Errors should be reset
        assert project.error_tracking["consecutive_errors"] == 0
        assert project.error_tracking["alert_suppressed"] is False
