"""
Tests for Telegram integration in the notification system.

Mocks _send_telegram and _load_bot_token to verify:
- Each notify function calls _send_telegram when rate limiter allows
- _send_telegram is NOT called when rate limiter blocks
- _send_telegram handles failures gracefully
- _load_bot_token reads from config path
- TELEGRAM_ENABLED=False disables sends
"""

import json
import os
import tempfile
from unittest.mock import patch, MagicMock, call

import pytest

from orchestrator.notifier import (
    RateLimiter,
    _send_telegram,
    _load_bot_token,
    notify_phase_complete,
    notify_timeout,
    notify_ready_for_build,
    notify_idle_reminder,
    notify_idle_autostore,
    notify_error,
    notify_cancellation_prompt,
    notify_trash_warning,
)

# Build token and env content without escape sequences
TOKEN_PARTS = ["abc123", "XYZ"]
EXPECTED_TOKEN = "".join(TOKEN_PARTS)
ENV_CONTENT = "OTHER_VAR=foo\nTELEGRAM_BOT_TOKEN=" + EXPECTED_TOKEN + "\nANOTHER_VAR=bar\n"


# ══════════════════════════════════════════════════════════════════════
# _load_bot_token Tests
# ══════════════════════════════════════════════════════════════════════

class TestLoadBotToken:
    def test_reads_token_from_env_file(self):
        """Should extract TELEGRAM_BOT_TOKEN from .env file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(ENV_CONTENT)
            f.flush()
            fname = f.name

        try:
            with patch("orchestrator.notifier.TELEGRAM_BOT_TOKEN_PATH", fname):
                token = _load_bot_token()
            assert token == EXPECTED_TOKEN
        finally:
            os.unlink(fname)

    def test_returns_none_on_missing_file(self):
        """Should return None if token file doesn't exist."""
        with patch("orchestrator.notifier.TELEGRAM_BOT_TOKEN_PATH", "/nonexistent/path.env"):
            token = _load_bot_token()
        assert token is None

    def test_returns_none_on_empty_file(self):
        """Should return None if file has no token line."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("OTHER_VAR=foo\n")
            f.flush()
            fname = f.name

        try:
            with patch("orchestrator.notifier.TELEGRAM_BOT_TOKEN_PATH", fname):
                token = _load_bot_token()
            assert token is None
        finally:
            os.unlink(fname)


# ══════════════════════════════════════════════════════════════════════
# _send_telegram Tests
# ══════════════════════════════════════════════════════════════════════

class TestSendTelegram:
    def test_returns_false_when_disabled(self):
        """Should return False immediately when TELEGRAM_ENABLED=False."""
        with patch("orchestrator.notifier.TELEGRAM_ENABLED", False):
            result = _send_telegram("test message")
        assert result is False

    def test_returns_false_when_no_token(self):
        """Should return False when bot token can't be loaded."""
        with patch("orchestrator.notifier.TELEGRAM_ENABLED", True), \
             patch("orchestrator.notifier._load_bot_token", return_value=None):
            result = _send_telegram("test message")
        assert result is False

    @patch("orchestrator.notifier.subprocess.run")
    def test_sends_via_curl(self, mock_run):
        """Should invoke curl with correct arguments."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )
        with patch("orchestrator.notifier.TELEGRAM_ENABLED", True), \
             patch("orchestrator.notifier._load_bot_token", return_value="tok123"), \
             patch("orchestrator.notifier.TELEGRAM_CHAT_ID", "12345"):
            result = _send_telegram("Hello World")

        assert result is True
        args = mock_run.call_args[0][0]
        assert "curl" in args
        assert "tok123" in " ".join(args)

    @patch("orchestrator.notifier.subprocess.run")
    def test_returns_false_on_curl_error(self, mock_run):
        """Should return False when curl returns non-zero."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        with patch("orchestrator.notifier.TELEGRAM_ENABLED", True), \
             patch("orchestrator.notifier._load_bot_token", return_value="tok123"):
            result = _send_telegram("test")
        assert result is False

    @patch("orchestrator.notifier.subprocess.run")
    def test_returns_false_on_api_error(self, mock_run):
        """Should return False when Telegram API returns ok=false."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"ok": False, "description": "Bad Request"}),
            stderr="",
        )
        with patch("orchestrator.notifier.TELEGRAM_ENABLED", True), \
             patch("orchestrator.notifier._load_bot_token", return_value="tok123"):
            result = _send_telegram("test")
        assert result is False

    @patch("orchestrator.notifier.subprocess.run")
    def test_returns_false_on_timeout(self, mock_run):
        """Should return False when curl times out."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="curl", timeout=15)
        with patch("orchestrator.notifier.TELEGRAM_ENABLED", True), \
             patch("orchestrator.notifier._load_bot_token", return_value="tok123"):
            result = _send_telegram("test")
        assert result is False

    @patch("orchestrator.notifier.subprocess.run")
    def test_returns_false_on_malformed_response(self, mock_run):
        """Should return False when response is not valid JSON."""
        mock_run.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
        with patch("orchestrator.notifier.TELEGRAM_ENABLED", True), \
             patch("orchestrator.notifier._load_bot_token", return_value="tok123"):
            result = _send_telegram("test")
        assert result is False


# ══════════════════════════════════════════════════════════════════════
# Integration: Notify functions call _send_telegram
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _fresh_rate_limiter():
    """Reset the module-level rate limiter before each test."""
    import orchestrator.notifier as _mod
    _orig = _mod._rate_limiter
    _mod._rate_limiter = RateLimiter()
    yield
    _mod._rate_limiter = _orig


class TestNotifySendsTelegram:
    """Verify each notify function triggers _send_telegram when allowed."""

    @patch("orchestrator.notifier._send_telegram", return_value=True)
    def test_phase_complete_sends(self, mock_send):
        msg = notify_phase_complete("tg-proj-1", "R1_ECHO", "echo")
        mock_send.assert_called_once_with(msg)

    @patch("orchestrator.notifier._send_telegram", return_value=True)
    def test_timeout_sends(self, mock_send):
        msg = notify_timeout("tg-proj-2", "R1_ECHO", "echo")
        mock_send.assert_called_once_with(msg)

    @patch("orchestrator.notifier._send_telegram", return_value=True)
    def test_ready_for_build_sends(self, mock_send):
        msg = notify_ready_for_build("tg-proj-3")
        mock_send.assert_called_once_with(msg)

    @patch("orchestrator.notifier._send_telegram", return_value=True)
    def test_idle_reminder_sends(self, mock_send):
        msg = notify_idle_reminder("tg-proj-4", 48)
        mock_send.assert_called_once_with(msg)

    @patch("orchestrator.notifier._send_telegram", return_value=True)
    def test_idle_autostore_sends(self, mock_send):
        msg = notify_idle_autostore("tg-proj-5")
        mock_send.assert_called_once_with(msg)

    @patch("orchestrator.notifier._send_telegram", return_value=True)
    def test_error_sends(self, mock_send):
        msg = notify_error("tg-proj-6", "Error", "details")
        mock_send.assert_called_once_with(msg)

    @patch("orchestrator.notifier._send_telegram", return_value=True)
    def test_cancellation_prompt_sends(self, mock_send):
        msg = notify_cancellation_prompt("tg-proj-7")
        mock_send.assert_called_once_with(msg)

    @patch("orchestrator.notifier._send_telegram", return_value=True)
    def test_trash_warning_sends(self, mock_send):
        msg = notify_trash_warning("tg-proj-8", 7)
        mock_send.assert_called_once_with(msg)


class TestNotifyRateLimitsTelegram:
    """Verify rate limiting gates Telegram sends."""

    @patch("orchestrator.notifier._send_telegram", return_value=True)
    def test_rate_limit_blocks_second_send(self, mock_send):
        """Second notification within 5 min should NOT send via Telegram."""
        with patch("orchestrator.notifier.time") as mock_time:
            mock_time.time.return_value = 5000.0
            notify_phase_complete("rl-proj", "R1_ECHO", "echo")
            assert mock_send.call_count == 1

            mock_time.time.return_value = 5100.0  # 100s later — still in cooldown
            notify_phase_complete("rl-proj", "R1_TRIPP", "tripp")
            assert mock_send.call_count == 1  # Still 1 — second was blocked

    @patch("orchestrator.notifier._send_telegram", return_value=True)
    def test_rate_limit_allows_after_cooldown(self, mock_send):
        """After 5 min cooldown, should send again."""
        with patch("orchestrator.notifier.time") as mock_time:
            mock_time.time.return_value = 5000.0
            notify_phase_complete("rl-proj-2", "R1_ECHO", "echo")
            assert mock_send.call_count == 1

            mock_time.time.return_value = 5301.0  # 301s later — past cooldown
            notify_phase_complete("rl-proj-2", "R1_TRIPP", "tripp")
            assert mock_send.call_count == 2

    @patch("orchestrator.notifier._send_telegram", return_value=True)
    def test_all_types_respect_rate_limit(self, mock_send):
        """All notification types should be gated by rate limiter.
        Uses unique project names per call since rate limiting is per-project."""
        with patch("orchestrator.notifier.time") as mock_time:
            mock_time.time.return_value = 6000.0
            notify_phase_complete("rl-pc", "R1_ECHO", "echo")
            notify_timeout("rl-to", "R1_TRIPP", "tripp")
            notify_ready_for_build("rl-rb")
            notify_idle_reminder("rl-ir", 48)
            notify_idle_autostore("rl-ia")
            notify_error("rl-er", "Error", "d")
            notify_cancellation_prompt("rl-cp")
            notify_trash_warning("rl-tw", 7)

            # All 8 should have sent (each is a unique project)
            assert mock_send.call_count == 8
