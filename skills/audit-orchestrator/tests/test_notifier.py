"""
Comprehensive tests for Audit Orchestrator — Phase 4: Notification System

Covers:
- Each notification type returns correct format
- Rate limiting prevents spam (within 5 min window)
- Rate limiting allows after 5 min window
- format_notification with actions
- format_notification without actions
- RateLimiter class behavior
"""

import time
from unittest.mock import patch

import pytest

from orchestrator.notifier import (
    RateLimiter,
    format_notification,
    notify_phase_complete,
    notify_timeout,
    notify_ready_for_build,
    notify_idle_reminder,
    notify_idle_autostore,
    notify_error,
    notify_cancellation_prompt,
    notify_trash_warning,
    get_rate_limiter,
)


# ══════════════════════════════════════════════════════════════════════
# format_notification Tests
# ══════════════════════════════════════════════════════════════════════

class TestFormatNotification:
    def test_without_actions(self):
        """format_notification without actions should produce emoji + heading."""
        result = format_notification("✅", "All done", "Details here")
        assert result == "✅ All done\nDetails here"

    def test_with_actions(self):
        """format_notification with actions should append bracketed buttons."""
        result = format_notification(
            "🎯", "Ready", "",
            actions=["YES", "NO", "CANCEL"],
        )
        assert "[YES]" in result
        assert "[NO]" in result
        assert "[CANCEL]" in result
        assert result == "🎯 Ready\n[YES] [NO] [CANCEL]"

    def test_with_empty_body(self):
        """format_notification with empty body should still format correctly."""
        result = format_notification("⏰", "Warning", "")
        assert result == "⏰ Warning"

    def test_with_none_actions(self):
        """format_notification with actions=None should omit actions line."""
        result = format_notification("❌", "Error", "Something broke", actions=None)
        assert "[" not in result  # No bracketed actions
        assert "❌ Error" in result
        assert "Something broke" in result

    def test_single_action(self):
        """format_notification with a single action."""
        result = format_notification("🗑️", "Warning", "", actions=["Rescue"])
        assert "[Rescue]" in result


# ══════════════════════════════════════════════════════════════════════
# Notification Type Tests
# ══════════════════════════════════════════════════════════════════════

class TestNotifyPhaseComplete:
    def test_returns_correct_format(self):
        msg = notify_phase_complete("my-project", "R1_ECHO", "echo")
        assert "✅" in msg
        assert "echo" in msg
        assert "R1_ECHO" in msg
        assert "my-project" in msg
        assert "finished" in msg

    def test_full_string_match(self):
        msg = notify_phase_complete("trip-mind", "R1_TRIPP", "tripp")
        assert msg == "✅ tripp finished R1_TRIPP for trip-mind"


class TestNotifyTimeout:
    def test_returns_correct_format(self):
        msg = notify_timeout("my-project", "R1_ECHO", "echo")
        assert "⏰" in msg
        assert "echo" in msg
        assert "timed out on" in msg
        assert "R1_ECHO" in msg
        assert "my-project" in msg

    def test_has_action_buttons(self):
        msg = notify_timeout("proj", "R2_TRIPP", "tripp")
        assert "[Extend +30min]" in msg
        assert "[Skip]" in msg
        assert "[Abort]" in msg


class TestNotifyReadyForBuild:
    def test_returns_correct_format(self):
        msg = notify_ready_for_build("my-project")
        assert "🎯" in msg
        assert "my-project" in msg
        assert "ready for build" in msg

    def test_has_action_buttons(self):
        msg = notify_ready_for_build("proj")
        assert "[✅ YES]" in msg
        assert "[📁 STORE]" in msg
        assert "[🗑️ TRASH]" in msg
        assert "[❌ CANCEL]" in msg


class TestNotifyIdleReminder:
    def test_returns_correct_format(self):
        msg = notify_idle_reminder("my-project", 48)
        assert "⏳" in msg
        assert "my-project" in msg
        assert "48h" in msg
        assert "waiting" in msg

    def test_float_hours(self):
        msg = notify_idle_reminder("proj", 72.5)
        assert "72.5h" in msg


class TestNotifyIdleAutostore:
    def test_returns_correct_format(self):
        msg = notify_idle_autostore("my-project")
        assert "📁" in msg
        assert "my-project" in msg
        assert "auto-stored" in msg
        assert "7 days" in msg
        assert "Restore" in msg


class TestNotifyError:
    def test_returns_correct_format(self):
        msg = notify_error("my-project", "JSONParse", "Malformed status file")
        assert "❌" in msg
        assert "my-project" in msg
        assert "JSONParse" in msg
        assert "Malformed status file" in msg


class TestNotifyCancellationPrompt:
    def test_returns_correct_format(self):
        msg = notify_cancellation_prompt("my-project")
        assert "❓" in msg
        assert "cancelling" in msg
        assert "my-project" in msg
        assert "reply with reason" in msg


class TestNotifyTrashWarning:
    def test_returns_correct_format(self):
        msg = notify_trash_warning("my-project", 7)
        assert "🗑️" in msg
        assert "my-project" in msg
        assert "7" in msg
        assert "auto-deleted" in msg

    def test_has_rescue_button(self):
        msg = notify_trash_warning("proj", 3)
        assert "[Rescue]" in msg

    def test_zero_days(self):
        msg = notify_trash_warning("proj", 0)
        assert "0 days" in msg


# ══════════════════════════════════════════════════════════════════════
# RateLimiter Tests
# ══════════════════════════════════════════════════════════════════════

class TestRateLimiter:
    def test_can_notify_new_project(self):
        """A new project should always be allowed."""
        rl = RateLimiter()
        assert rl.can_notify("new-project") is True

    def test_cannot_notify_within_cooldown(self):
        """Should not allow notification within 5 minutes."""
        rl = RateLimiter()
        with patch("orchestrator.notifier.time") as mock_time:
            mock_time.time.return_value = 1000.0
            rl.record("my-project")

            # 1 minute later — still in cooldown
            mock_time.time.return_value = 1060.0
            assert rl.can_notify("my-project") is False

    def test_can_notify_after_cooldown(self):
        """Should allow notification after 5 minutes."""
        rl = RateLimiter()
        with patch("orchestrator.notifier.time") as mock_time:
            mock_time.time.return_value = 1000.0
            rl.record("my-project")

            # 5 minutes + 1 second later
            mock_time.time.return_value = 1301.0
            assert rl.can_notify("my-project") is True

    def test_record_updates_timestamp(self):
        """record() should update the last_notified timestamp."""
        rl = RateLimiter()
        with patch("orchestrator.notifier.time") as mock_time:
            mock_time.time.return_value = 500.0
            rl.record("proj")
            assert rl._last_notified["proj"] == 500.0

            mock_time.time.return_value = 600.0
            rl.record("proj")
            assert rl._last_notified["proj"] == 600.0

    def test_different_projects_independent(self):
        """Rate limiting should be per-project, not global."""
        rl = RateLimiter()
        with patch("orchestrator.notifier.time") as mock_time:
            mock_time.time.return_value = 1000.0
            rl.record("project-a")

            # project-b should still be allowed
            assert rl.can_notify("project-b") is True
            # project-a should be blocked
            assert rl.can_notify("project-a") is False

    def test_time_until_next_ready(self):
        """time_until_next should return 0 when ready."""
        rl = RateLimiter()
        with patch("orchestrator.notifier.time") as mock_time:
            mock_time.time.return_value = 1000.0
            assert rl.time_until_next("proj") == 0.0

    def test_time_until_next_counting_down(self):
        """time_until_next should return remaining seconds."""
        rl = RateLimiter()
        with patch("orchestrator.notifier.time") as mock_time:
            mock_time.time.return_value = 1000.0
            rl.record("proj")

            mock_time.time.return_value = 1100.0  # 100s elapsed
            remaining = rl.time_until_next("proj")
            assert remaining == 200.0

    def test_time_until_next_at_boundary(self):
        """time_until_next should return 0 at exactly the cooldown boundary."""
        rl = RateLimiter()
        with patch("orchestrator.notifier.time") as mock_time:
            mock_time.time.return_value = 1000.0
            rl.record("proj")

            mock_time.time.return_value = 1300.0  # exactly 5 min
            remaining = rl.time_until_next("proj")
            assert remaining == 0.0


# ══════════════════════════════════════════════════════════════════════
# Integration: Rate Limiting with Notifications
# ══════════════════════════════════════════════════════════════════════

class TestNotificationRateLimiting:
    def test_notifications_record_in_rate_limiter(self):
        """Each notification function should record in the rate limiter."""
        rl = get_rate_limiter()
        with patch("orchestrator.notifier.time") as mock_time:
            mock_time.time.return_value = 2000.0

            notify_phase_complete("test-proj", "R1_ECHO", "echo")
            assert rl.can_notify("test-proj") is False

    def test_all_notification_types_record_rate_limit(self):
        """All notification types should record their project in the rate limiter."""
        rl = get_rate_limiter()
        with patch("orchestrator.notifier.time") as mock_time:
            mock_time.time.return_value = 3000.0

            notify_phase_complete("proj-a", "R1_ECHO", "echo")
            notify_timeout("proj-b", "R1_TRIPP", "tripp")
            notify_ready_for_build("proj-c")
            notify_idle_reminder("proj-d", 48)
            notify_idle_autostore("proj-e")
            notify_error("proj-f", "Error", "details")
            notify_cancellation_prompt("proj-g")
            notify_trash_warning("proj-h", 7)

            # All should now be rate-limited
            mock_time.time.return_value = 3100.0
            assert rl.can_notify("proj-a") is False
            assert rl.can_notify("proj-b") is False
            assert rl.can_notify("proj-c") is False
            assert rl.can_notify("proj-d") is False
            assert rl.can_notify("proj-e") is False
            assert rl.can_notify("proj-f") is False
            assert rl.can_notify("proj-g") is False
            assert rl.can_notify("proj-h") is False

    def test_rate_limit_prevents_duplicate_within_window(self):
        """Sending two notifications for same project within 5 min should both return strings."""
        with patch("orchestrator.notifier.time") as mock_time:
            mock_time.time.return_value = 4000.0
            msg1 = notify_phase_complete("proj", "R1_ECHO", "echo")

            mock_time.time.return_value = 4100.0
            msg2 = notify_phase_complete("proj", "R1_TRIPP", "tripp")

            # Both return valid messages
            assert "✅" in msg1
            assert "✅" in msg2
            # But the rate limiter should block further notifications
            rl = get_rate_limiter()
            mock_time.time.return_value = 4200.0
            assert rl.can_notify("proj") is False
