"""Strict UUIDv4 message identifiers."""

import uuid


def generate_message_id() -> str:
    return uuid.uuid4().hex


def validate_message_id(message_id: object) -> bool:
    if not isinstance(message_id, str) or len(message_id) != 32 or not message_id.islower():
        return False
    try:
        value = int(message_id, 16)
    except ValueError:
        return False
    return ((value >> 76) & 0xF) == 4 and ((value >> 62) & 0x3) == 0b10
