from enum import Enum
from typing import Union, List, Any, Dict
from pydantic import BaseModel


class CommandOptions(Enum):
    PRE_LOAD_IMAGE = 'pre_load'
    RUN_POD = 'run_pod'
    DELETE_POD = 'delete_pod'
    DELETE_ALL_PODS = 'delete_all_pods'
    GET_POD_DETAILS = 'get_pod_details'


class CommandResult(Enum):
    SUCCESS = 'Success'
    FAILURE = 'Failure'


class ExecutionRequest(BaseModel):
    id: int
    command: CommandOptions
    arguments: Dict[str, Union[Dict[str, str], str]]


class ExecutionResponse(BaseModel):
    id: int
    result: CommandResult
    description: str
    extra: Any


class HandshakeReceptionMessage(BaseModel):
    ip: str
    port: int
    secret_key: bytes


class HandshakeStatus(Enum):
    SUCCESS = 0
    INITIALIZING = 1
    FAILURE = 2


class HandshakeResponse(BaseModel):
    STATUS: HandshakeStatus
    DESCRIPTION: str


class PodDetails(BaseModel):
    pod_name: str
    cpu_utilization: str
    memory_utilization: str
    measurement_window: str


class NamespaceDetails(BaseModel):
    pod_details: List[PodDetails]
