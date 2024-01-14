import socket

from tpc_backend_libraries.api.cluster_access.v1.node_registrar import NodeDetails
import uuid


def get_machine_unique_id() -> NodeDetails:
    return NodeDetails(
        name=socket.gethostname(),
        id=uuid.UUID(int=uuid.getnode())
    )
