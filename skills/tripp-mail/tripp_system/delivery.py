"""Idempotent delivery adapter contract."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class PermanentError(Exception):
    """The delivery cannot succeed through retrying."""


class DeliveryAdapter(ABC):
    @abstractmethod
    def __call__(self, delivery: dict[str, Any], operation_key: str) -> None:
        """Deliver once; the operation key must be honored idempotently."""


class RealDeliveryAdapter(DeliveryAdapter):
    def __init__(self, handler: Callable[[dict[str, Any], str], None]):
        self.handler = handler

    def __call__(self, delivery: dict[str, Any], operation_key: str) -> None:
        self.handler(delivery, operation_key)
