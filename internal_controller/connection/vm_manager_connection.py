import asyncio
import json
import logging
import threading
from concurrent.futures import ProcessPoolExecutor
from json import JSONDecodeError
from typing import Final

import socketio
# from crypto.Cipher import AES
from pydantic import ValidationError
from websockets.exceptions import ConnectionClosedOK
from websockets.server import serve

from internal_controller.kubernetes.kube_handler import KubeHandler
from internal_controller.connection.schema import HandshakeResponse, HandshakeStatus
from utilities.constants import HELLO_MSG
from utilities.messages import PassThroughMessage
from worker_manager.vm_manager.schema import HandshakeReceptionMessage


class ConnectionHandler(socketio.AsyncClientNamespace):
    NAMESPACE: Final[str] = '/vm_connection'

    def __init__(self, port: int):
        super().__init__(ConnectionHandler.NAMESPACE)

        self.stop_event = threading.Event()
        self.loop = asyncio.get_event_loop()
        self.stop = self.loop.run_in_executor(None, self.stop_event.wait)
        self._port = port
        self._kube_handler = KubeHandler()
        self._initialization_data = None
        self._client = None
        self._cypher = None  # TODO ADD

    @property
    def initialization_data(self) -> HandshakeReceptionMessage:
        return self._initialization_data

    @staticmethod
    def prepare_kube(kube_handler: 'KubeHandler'):
        kube_handler.initialize()

    async def handler(self, websocket, path):
        while True:
            try:
                data = json.loads(await websocket.recv())
                response = HandshakeReceptionMessage(**data)
                if not self._kube_handler.kube_ready:
                    await websocket.send(
                        HandshakeResponse(STATUS=HandshakeStatus.INITIALIZING, DESCRIPTION="Installing k3s",
                                          SECRET_KEY=response.secret_key).model_dump_json())
                    await self.loop.run_in_executor(ProcessPoolExecutor(), ConnectionHandler.prepare_kube,
                                                    self._kube_handler)

                if not self._kube_handler.kube_ready:
                    err_msg = 'Failed to install kubernetes.. terminating'
                    await websocket.send(HandshakeResponse(STATUS=HandshakeStatus.FAILURE, DESCRIPTION=err_msg,
                                                           SECRET_KEY=response.secret_key).model_dump_json())
                    await self.close_comms(websocket)
                    raise Exception(err_msg)

                self._initialization_data = response
                await websocket.send(HandshakeResponse(STATUS=HandshakeStatus.SUCCESS, DESCRIPTION="Details received",
                                                       SECRET_KEY=response.secret_key).model_dump_json())
                await self.close_comms(websocket)
                return

            except ValidationError as e:
                logging.error(
                    f"Received invalid internal initialization data, validation error: {e.cause}, worker will be ignored")

            except ConnectionClosedOK as e:
                return
            except ConnectionResetError as e:
                return

            except JSONDecodeError as e:
                logging.error(
                    f"Received non-json message.. ignoring")
                return

    async def close_comms(self, websocket):
        await websocket.close()
        self.stop_event.set()

    async def run_until_handshake_complete(self):
        async with serve(self.handler, "0.0.0.0", self._port):
            await self.stop

    async def connect_to_server(self):
        self._client = socketio.AsyncClient()
        self._client.register_namespace(self)
        await self._client.connect(f'http://{self.initialization_data.ip}:{self.initialization_data.port}')
        hello_msg = PassThroughMessage(DATA=HELLO_MSG, TAG='')
        await self._client.emit(event='hello', data=hello_msg.model_dump_json(), namespace=ConnectionHandler.NAMESPACE)

    def run(self):
        self.loop.run_until_complete(self.run_until_handshake_complete())
        self.loop.run_until_complete(self.connect_to_server())
        print("Connection accepted")

        while True:
            self.loop.run_until_complete(asyncio.sleep(1))
