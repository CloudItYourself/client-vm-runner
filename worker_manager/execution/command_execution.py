import json
from json import JSONDecodeError

import websockets
from pydantic import ValidationError
from websockets.exceptions import ConnectionClosed

from utilities.messages import ExecutionRequest, ExecutionResponse, CommandResult
from worker_manager.vm_manager.internal_controller_comms import InternalControllerComms


class CommandExecution:
    def __init__(self, server_ip: str, server_port: int, path: str, internal_comm_handler: InternalControllerComms):
        self._server_ip = server_ip
        self._server_port = server_port
        self._path = path
        self._client = None
        self._internal_comm_handler = internal_comm_handler
        self._should_terminate = False

    async def initialize(self):
        self._client = await websockets.connect(f"ws://{self._server_ip}:{self._server_port}/{self._path}")

    @property
    def should_terminate(self):
        return self._should_terminate

    async def process_command(self):
        try:
            data = await self._client.recv()
            json_data = json.loads(data)
            execution_request = ExecutionRequest(**json_data)
            await self._client.send(await self._internal_comm_handler.send_request(execution_request))
        except JSONDecodeError as e:
            await self._client.send(
                ExecutionResponse(id=-1, result=CommandResult.FAILURE, description=f'Json decode error: {e}',
                                  extra={}).model_dump_json())
        except ValidationError as e:
            await self._client.send(
                ExecutionResponse(id=-1, result=CommandResult.FAILURE, description=f'Request validation error: {e}',
                                  extra={}).model_dump_json())
        except ConnectionClosed:
            self._should_terminate = True
