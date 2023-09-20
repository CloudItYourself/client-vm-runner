from enum import Enum
from typing import Final, Dict, Any, TypedDict

HANDSHAKE_RECEPTION_SCHEMA: Final[Dict[str, Any]] = {
    "type": "object",
    "properties": {
        "ip": {"type": "string"},
        "port": {"type": "number"},
        "secret_key": {"type": "string"},
    },
    "required": ["ip", "port", "secret_key"],
    "additionalProperties": False
}


class HandshakeStatus(Enum):
    SUCCESS = 0
    INITIALIZING = 1
    FAILURE = 2


class HandshakeResponse(TypedDict):
    STATUS: HandshakeStatus
    DESCRIPTION: str
    SECRET_KEY: str
