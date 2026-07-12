"""Compatibility exception exports."""

from .delivery import PermanentError
from .worker import SystemHaltError, TransientError


class TrippError(Exception):
    """Base error for application-level integrations."""


__all__ = ["PermanentError", "SystemHaltError", "TransientError", "TrippError"]
