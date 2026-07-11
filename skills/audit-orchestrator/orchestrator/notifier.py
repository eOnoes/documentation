"""
Audit Orchestrator — Notification System

Sends Eddie brief Telegram updates at key milestones. All notification
functions return the formatted message string for testing.
Live Telegram sending is gated behind TELEGRAM_ENABLED in config.

Includes rate limiting: max 1 notification per project per 5 minutes.
"""

import time
import subprocess
import logging
import re

from .config import TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN_PATH, TELEGRAM_ENABLED

logger = logging.getLogger(__name__)

# ── Telegram Sender ──────────────────────────────────────────────────

def _load_bot_token() -> str | None:
    """Read the bot token from the .env file. Returns None on failure."""
    try:
        with open(TELEGRAM_BOT_TOKEN_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    return line.split("=", 1)[1]
    except (OSError, FileNotFoundError) as e:
        logger.warning("Could not read bot token from %s: %s", TELEGRAM_BOT_TOKEN_PATH, e)
    return None


def _send_telegram(message: str) -> bool:
    """
    Send a message to Eddie via Telegram using curl.

    Returns True on success, False on failure.
    Failures are logged but never raised — notifications are best-effort.
    """
    if not TELEGRAM_ENABLED:
        return False

    token = _load_bot_token()
    if not token:
        logger.warning("Telegram bot token not available — skipping send")
        return False

    # Sanitize message for shell: escape single quotes in the message text.
    # We pass the message via --data-urlencode which handles URL encoding,
    # but we also need to escape for the shell invocation.
    safe_message = message.replace("\\", "\\\\").replace('"', '\\"')

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    cmd = [
        "curl", "-s", "-X", "POST", url,
        "--data-urlencode", f"chat_id={TELEGRAM_CHAT_ID}",
        "--data-urlencode", f"text={message}",
        "--data-urlencode", "parse_mode=Markdown",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            logger.warning("curl failed (rc=%d): %s", result.returncode, result.stderr[:200])
            return False

        # Check for Telegram API errors in response
        import json
        try:
            resp = json.loads(result.stdout)
            if not resp.get("ok"):
                logger.warning("Telegram API error: %s", resp.get("description", "unknown"))
                return False
        except (json.JSONDecodeError, KeyError):
            logger.warning("Could not parse Telegram response: %s", result.stdout[:200])
            return False

        return True
    except subprocess.TimeoutExpired:
        logger.warning("Telegram send timed out (15s)")
        return False
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)
        return False


# ── Rate Limiter ────────────────────────────────────────────────────────
class RateLimiter:
    """
    Max 1 notification per project per 5 minutes.
    Uses dict of {project: last_notified_timestamp}.
    """

    COOLDOWN_SECONDS = 300  # 5 minutes

    def __init__(self):
        self._last_notified: dict[str, float] = {}

    def can_notify(self, project_name: str) -> bool:
        """Return True if enough time has passed since the last notification."""
        last = self._last_notified.get(project_name)
        if last is None:
            return True
        return (time.time() - last) >= self.COOLDOWN_SECONDS

    def record(self, project_name: str) -> None:
        """Record that a notification was sent for this project."""
        self._last_notified[project_name] = time.time()

    def time_until_next(self, project_name: str) -> float:
        """Seconds remaining before next notification is allowed (0 if ready)."""
        last = self._last_notified.get(project_name)
        if last is None:
            return 0.0
        remaining = self.COOLDOWN_SECONDS - (time.time() - last)
        return max(remaining, 0.0)


# ── Module-level rate limiter instance ─────────────────────────────────
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Return the module-level RateLimiter instance."""
    return _rate_limiter


# ── Format Helper ───────────────────────────────────────────────────────
def format_notification(
    emoji: str,
    heading: str,
    body: str,
    actions: list[str] | None = None,
) -> str:
    """
    Format a notification message.

    Args:
        emoji: Leading emoji for the message.
        heading: Short heading text.
        body: Main body text.
        actions: Optional list of action button labels (e.g. ["✅ YES", "📁 STORE"]).

    Returns:
        Formatted string with emoji, heading, body, and optional actions.
    """
    parts = [f"{emoji} {heading}"]

    if body:
        parts.append(body)

    if actions:
        parts.append(" ".join(f"[{a}]" for a in actions))

    return "\n".join(parts)


# ── Notification Functions ─────────────────────────────────────────────

def notify_phase_complete(project_name: str, phase: str, agent: str) -> str:
    """
    Brief notification when an agent finishes a phase.

    Returns: "✅ {agent} finished {phase} for {project_name}"
    """
    msg = format_notification(
        emoji="✅",
        heading=f"{agent} finished {phase} for {project_name}",
        body="",
    )
    if _rate_limiter.can_notify(project_name):
        _rate_limiter.record(project_name)
        _send_telegram(msg)
    return msg


def notify_timeout(project_name: str, phase: str, agent: str) -> str:
    """
    Alert notification when an agent times out.

    Returns: "⏰ {agent} timed out on {phase} for {project_name}. [Extend +30min] / [Skip] / [Abort]"
    """
    msg = format_notification(
        emoji="⏰",
        heading=f"{agent} timed out on {phase} for {project_name}.",
        body="",
        actions=["Extend +30min", "Skip", "Abort"],
    )
    if _rate_limiter.can_notify(project_name):
        _rate_limiter.record(project_name)
        _send_telegram(msg)
    return msg


def notify_ready_for_build(project_name: str) -> str:
    """
    Full notification when project is ready for build.

    Returns: "🎯 {project_name} is ready for build! [✅ YES] [📁 STORE] [🗑️ TRASH] [❌ CANCEL]"
    """
    msg = format_notification(
        emoji="🎯",
        heading=f"{project_name} is ready for build!",
        body="",
        actions=["✅ YES", "📁 STORE", "🗑️ TRASH", "❌ CANCEL"],
    )
    if _rate_limiter.can_notify(project_name):
        _rate_limiter.record(project_name)
        _send_telegram(msg)
    return msg


def notify_idle_reminder(project_name: str, hours_idle: int | float) -> str:
    """
    Reminder when project has been idle at READY_FOR_BUILD.

    Returns: "⏳ {project_name} has been waiting {hours_idle}h for your call"
    """
    msg = format_notification(
        emoji="⏳",
        heading=f"{project_name} has been waiting {hours_idle}h for your call",
        body="",
    )
    if _rate_limiter.can_notify(project_name):
        _rate_limiter.record(project_name)
        _send_telegram(msg)
    return msg


def notify_idle_autostore(project_name: str) -> str:
    """
    Notification when project is auto-stored after 7 days idle.

    Returns: "📁 {project_name} auto-stored after 7 days. Restore anytime."
    """
    msg = format_notification(
        emoji="📁",
        heading=f"{project_name} auto-stored after 7 days. Restore anytime.",
        body="",
    )
    if _rate_limiter.can_notify(project_name):
        _rate_limiter.record(project_name)
        _send_telegram(msg)
    return msg


def notify_error(project_name: str, error_type: str, details: str) -> str:
    """
    Error notification.

    Returns: "❌ Error on {project_name}: {error_type} — {details}"
    """
    msg = format_notification(
        emoji="❌",
        heading=f"Error on {project_name}: {error_type} — {details}",
        body="",
    )
    if _rate_limiter.can_notify(project_name):
        _rate_limiter.record(project_name)
        _send_telegram(msg)
    return msg


def notify_cancellation_prompt(project_name: str) -> str:
    """
    Prompt Eddie for a cancellation reason.

    Returns: "❓ Why are you cancelling {project_name}? (reply with reason)"
    """
    msg = format_notification(
        emoji="❓",
        heading=f"Why are you cancelling {project_name}? (reply with reason)",
        body="",
    )
    if _rate_limiter.can_notify(project_name):
        _rate_limiter.record(project_name)
        _send_telegram(msg)
    return msg


def notify_trash_warning(project_name: str, days_left: int) -> str:
    """
    Warning when project is approaching auto-deletion in trash.

    Returns: "🗑️ {project_name} will be auto-deleted in {days_left} days. [Rescue]"
    """
    msg = format_notification(
        emoji="🗑️",
        heading=f"{project_name} will be auto-deleted in {days_left} days.",
        body="",
        actions=["Rescue"],
    )
    if _rate_limiter.can_notify(project_name):
        _rate_limiter.record(project_name)
        _send_telegram(msg)
    return msg
