import asyncio
import json
import logging
import pathlib
import ssl
import tempfile
import threading
from internal_controller.kubernetes_handling.kube_handler import KubeHandler

from concurrent.futures import ProcessPoolExecutor
from json import JSONDecodeError
from typing import Final

import aiohttp
import socketio
from pydantic import ValidationError
from websockets.exceptions import ConnectionClosed
from websockets.server import serve

from internal_controller.connection.schema import HandshakeResponse, HandshakeStatus
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
                    err_msg = 'Failed to install kubernetes_handling.. terminating'
                    await websocket.send(
                        HandshakeResponse(STATUS=HandshakeStatus.FAILURE, DESCRIPTION=err_msg).model_dump_json())
                    await self.close_comms(websocket)
                    raise Exception(err_msg)

                self._initialization_data = response
                await websocket.send(
                    HandshakeResponse(STATUS=HandshakeStatus.SUCCESS, DESCRIPTION="Details received").model_dump_json())
                await self.close_comms(websocket)
                return

            except ValidationError as e:
                logging.error(
                    f"Received invalid internal initialization data, validation error: {e.cause}, worker will be ignored")

            except ConnectionClosed as e:
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
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

        with tempfile.TemporaryDirectory() as tmpdir:
            cert_file = (pathlib.Path(tmpdir) / 'cert.pem')
            cert_file.write_bytes(self.initialization_data.secret_key)
            ssl_context.load_verify_locations(cert_file.absolute())

        connector = aiohttp.TCPConnector(ssl=ssl_context)
        http_session = aiohttp.ClientSession(connector=connector)
        self._client = socketio.AsyncClient(http_session=http_session)
        self._client.register_namespace(self)

        await self._client.connect(f'https://{self.initialization_data.ip}:{self.initialization_data.port}')

    def run(self):
        self.loop.run_until_complete(self.run_until_handshake_complete())
        self.loop.run_until_complete(self.connect_to_server())
        print("Connection accepted")

        while True:
            self.loop.run_until_complete(asyncio.sleep(1))
