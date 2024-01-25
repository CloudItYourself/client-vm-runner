import socket

from ciy_backend_libraries.api.cluster_access.v1.node_registrar import NodeDetails
import uuid


def get_machine_unique_id() -> NodeDetails:
    return NodeDetails(
        name=socket.gethostname(),
        id=str(uuid.getnode())
    )