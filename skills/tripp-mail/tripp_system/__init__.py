"""TRIPP.SYSTEM v8.5 reliable message delivery."""

from .audit import AuditService
from .config import Configuration, load_config
from .credential_service import CredentialService
from .database import Database
from .delivery import DeliveryAdapter, PermanentError, RealDeliveryAdapter
from .id_generator import generate_message_id, validate_message_id
from .models import AuditEntry, Delivery, Message
from .reaper import LeaseReaper
from .worker import Worker

__version__ = "8.5.0"
__all__ = [
    "AuditEntry", "AuditService", "Configuration", "CredentialService", "Database",
    "Delivery", "DeliveryAdapter", "LeaseReaper", "Message", "PermanentError",
    "RealDeliveryAdapter", "Worker", "generate_message_id", "load_config",
    "validate_message_id",
]
