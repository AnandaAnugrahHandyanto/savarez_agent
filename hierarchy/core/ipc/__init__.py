"""Inter-process communication for agent coordination."""

from hierarchy.core.ipc.cleanup import MessageCleanup
from hierarchy.core.ipc.exceptions import (
    DeliveryError,
    InvalidMessageType,
    InvalidRecipient,
    IPCError,
    MessageBusError,
    MessageExpired,
    MessageNotFound,
)
from hierarchy.core.ipc.interface import (
    MessageHandler,
    MessageRouter,
    ProfileActivator,
)
from hierarchy.core.ipc.message_bus import MessageBus
from hierarchy.core.ipc.models import (
    DEFAULT_TTL,
    Message,
    MessagePriority,
    MessageStatus,
    MessageType,
    VALID_STATUS_TRANSITIONS,
    generate_correlation_id,
    generate_message_id,
)
from hierarchy.core.ipc.protocol import MessageProtocol
from hierarchy.core.ipc.schema import init_ipc_db, get_schema_version

__all__ = [
    # Core
    "MessageBus",
    "MessageProtocol",
    "MessageCleanup",
    # Schema
    "init_ipc_db",
    "get_schema_version",
    # Models
    "Message",
    "MessageType",
    "MessagePriority",
    "MessageStatus",
    "VALID_STATUS_TRANSITIONS",
    "DEFAULT_TTL",
    "generate_message_id",
    "generate_correlation_id",
    # Interfaces
    "MessageHandler",
    "MessageRouter",
    "ProfileActivator",
    # Exceptions
    "IPCError",
    "MessageNotFound",
    "InvalidRecipient",
    "InvalidMessageType",
    "MessageExpired",
    "MessageBusError",
    "DeliveryError",
]
