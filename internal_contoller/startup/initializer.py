import asyncio
import json
import logging
import threading
from concurrent.futures import ProcessPoolExecutor
from json import JSONDecodeError
from typing import Union, Dict

import jsonschema
from jsonschema.exceptions import ValidationError
from websockets.server import serve

from internal_contoller.kubernetes.kube_handler import KubeHandler
from internal_contoller.startup.schema import HANDSHAKE_RECEPTION_SCHEMA, HandshakeResponse, HandshakeStatus


class Initializer:
    def __init__(self, port: int):
        self.stop_event = threading.Event()
        self.loop = asyncio.get_event_loop()
        self.stop = self.loop.run_in_executor(None, self.stop_event.wait)
        self._port = port
        self._kube_handler = KubeHandler()
        self._initialization_data = None

    @property
    def initialization_data(self) -> Dict[str, Union[str, int]]:
        return self._initialization_data

    def prepare_kube(self):
        self._kube_handler.initialize()

    async def handler(self, websocket, path):
        while True:
            try:
                data = json.loads(await websocket.recv())
                jsonschema.validate(data, HANDSHAKE_RECEPTION_SCHEMA)
                if not self._kube_handler.kube_ready:
                    await websocket.send(json.dumps(
                        HandshakeResponse(STATUS=HandshakeStatus.INITIALIZING, DESCRIPTION="Installing k3s",
                                          SECRET_KEY=data['secret_key'])))
                    await self.loop.run_in_executor(ProcessPoolExecutor(), self.prepare_kube)

                if not self._kube_handler.kube_ready:
                    err_msg = 'Failed to install kubernetes.. terminating'
                    await websocket.send(
                        json.dumps(HandshakeResponse(STATUS=HandshakeStatus.FAILURE, DESCRIPTION=err_msg,
                                                     SECRET_KEY=data['secret_key'])))
                    self.stop_event.set()
                    raise Exception(err_msg)

                self._initialization_data = data
                await websocket.send(
                    json.dumps(HandshakeResponse(STATUS=HandshakeStatus.SUCCESS, DESCRIPTION="Details received",
                                                 SECRET_KEY=data['secret_key'])))
                self.stop_event.set()

            except ValidationError as e:
                logging.error(
                    f"Received invalid internal initialization data, validation error: {e.cause}, worker will be ignored")
            except JSONDecodeError as e:
                logging.error(
                    f"Received non-json message.. ignoring")

    async def run_until_handshake_complete(self):
        async with serve(self.handler, "localhost", self._port):
            await self.stop

    def run(self):
        self.loop.run_until_complete(self.run_until_handshake_complete())
        print("Connection accepted")
