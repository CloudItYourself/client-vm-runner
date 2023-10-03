import asyncio
import json
import logging
from json import JSONDecodeError
from typing import Final
from asyncio import Lock

import socketio
import websockets
from pydantic import ValidationError
from websockets.exceptions import ConnectionClosed, WebSocketException

from utilities.messages import ExecutionRequest, ExecutionResponse, CommandResult
from worker_manager import LOGGER_NAME
from worker_manager.monitoring.messages import WorkerDiscoveryMessage
from worker_manager.monitoring.worker_manager_handler import WorkerManagersConnectionHandler
from worker_manager.vm_manager.internal_controller_comms import InternalControllerComms


class CommandExecution:
    EXECUTION_PATH: Final[str] = 'worker_execution'

    def __init__(self, server_ip: str, server_port: int, internal_comm_handler: InternalControllerComms,
                 sio_object: socketio.AsyncClient):
        self._logger = logging.getLogger(LOGGER_NAME)
        self._server_ip = server_ip
        self._server_port = server_port
        self._client = None
        self._internal_comm_handler = internal_comm_handler
        self._sio = sio_object

    async def wait_for_connection(self) -> None:
        self._logger.info(
            f"Trying to connect to ws://{self._server_ip}:{self._server_port}/{CommandExecution.EXECUTION_PATH}")
        while True:
            try:
                current_sio = self._sio.get_sid(WorkerManagersConnectionHandler.NAMESPACE)
                if current_sio is not None:
                    self._client = await websockets.connect(
                        f"ws://{self._server_ip}:{self._server_port}/{CommandExecution.EXECUTION_PATH}")
                    await self._client.send(WorkerDiscoveryMessage(
                        worker_id=self._sio.get_sid(WorkerManagersConnectionHandler.NAMESPACE)).model_dump_json())
                    self._logger.info("Websocket connected successfully to connection broker")
                else:
                    await asyncio.sleep(0.2)
                return
            except WebSocketException as e:
                pass
            except ConnectionRefusedError as e:
                pass

    async def process_command(self) -> None:
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
        except WebSocketException:
            self._logger.info("Abruptly disconnected from server")
            await self._client.close()
            await self.wait_for_connection()

        except ConnectionRefusedError as e:
            self._logger.info("Abruptly disconnected from server")
            await self._client.close()
            await self.wait_for_connection()

    @staticmethod
    async def background_task(command_executor: 'CommandExecution') -> None:
        while True:
            await command_executor.process_command()
