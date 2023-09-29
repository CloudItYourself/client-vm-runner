from enum import Enum
from plistlib import Dict
from typing import Union
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
    id: str
    command: CommandOptions
    arguments: Dict[str, Union[Dict[str, str], str]]


class ExecutionResponse(BaseModel):
    id: str
    result: CommandResult
    description: str


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
