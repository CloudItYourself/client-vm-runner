from enum import Enum
from pydantic import BaseModel
from ciy_backend_libraries.api.cluster_access.v1.node_registrar import NodeDetails


class HandshakeReceptionMessage(BaseModel):
    ip: str
    port: int
    secret_key: bytes

    server_url: str
    machine_unique_identification: NodeDetails


class HandshakeStatus(Enum):
    SUCCESS = 0
    INITIALIZING = 1
    FAILURE = 2


class HandshakeResponse(BaseModel):
    STATUS: HandshakeStatus
    DESCRIPTION: str
