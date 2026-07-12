"""Typed records representing the three durable entities."""

from dataclasses import dataclass
from typing import Any, Mapping

from .id_generator import generate_message_id, validate_message_id


@dataclass(frozen=True, slots=True)
class Message:
    id: str
    type: str
    sender: str
    recipient: str
    body: str
    subject: str | None = None
    priority: int = 0
    state: str = "pending"
    created_at: str | None = None
    expires_at: str | None = None
    content_hash: str = ""

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Message":
        fields = cls.__dataclass_fields__
        return cls(**{name: row[name] for name in fields if name in row.keys()})


@dataclass(frozen=True, slots=True)
class Delivery:
    id: int
    message_id: str
    recipient_id: str
    state: str = "pending"
    claimed_by: str | None = None
    claimed_at: str | None = None
    lease_expires_at: str | None = None
    lease_fencing_token: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    next_attempt_at: str | None = None
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class AuditEntry:
    id: int
    event_id: str
    action: str
    actor: str
    previous_hash: str
    record_hash: str
    message_id: str | None = None
    delivery_id: int | None = None
    details: str | None = None
    timestamp: str | None = None
    signature: str | None = None


__all__ = ["Message", "Delivery", "AuditEntry", "generate_message_id", "validate_message_id"]
