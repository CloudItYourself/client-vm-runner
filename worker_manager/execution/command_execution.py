import json
from json import JSONDecodeError
from typing import Final

import websockets
from pydantic import ValidationError
from websockets.exceptions import ConnectionClosed

from utilities.messages import ExecutionRequest, ExecutionResponse, CommandResult
from worker_manager.monitoring.messages import WorkerDiscoveryMessage
from worker_manager.vm_manager.internal_controller_comms import InternalControllerComms


class CommandExecution:
    EXECUTION_PATH: Final[str] = 'worker_execution'

    def __init__(self, server_ip: str, server_port: int, internal_comm_handler: InternalControllerComms,
                 unique_id: str):
        self._server_ip = server_ip
        self._server_port = server_port
        self._client = None
        self._internal_comm_handler = internal_comm_handler
        self._should_terminate = False
        self._unique_id = unique_id

    async def initialize(self):
        self._client = await websockets.connect(
            f"ws://{self._server_ip}:{self._server_port}/{CommandExecution.EXECUTION_PATH}")
        await self._client.send(WorkerDiscoveryMessage(worker_id=self._unique_id).model_dump_json())

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

    @staticmethod
    async def background_task(command_executor: 'CommandExecution'):
        while True:
            await command_executor.process_command()
