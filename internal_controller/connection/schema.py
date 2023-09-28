from enum import Enum
from pydantic import BaseModel


class HandshakeStatus(Enum):
    SUCCESS = 0
    INITIALIZING = 1
    FAILURE = 2


class HandshakeResponse(BaseModel):
    STATUS: HandshakeStatus
    DESCRIPTION: str
