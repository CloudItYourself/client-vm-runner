import asyncio
import json
import logging
import pathlib
import random
import ssl
import string
import tempfile
import threading

import aiohttp
import websockets
from ciy_backend_libraries.api.cluster_access.v1.node_registrar import RegistrationDetails

from internal_controller.installers.environment_installer import EnvironmentInstaller

from concurrent.futures import ProcessPoolExecutor
from json import JSONDecodeError
from typing import Final

from pydantic import ValidationError
from websockets.exceptions import ConnectionClosed
from websockets.server import serve
from utilities.messages import HandshakeResponse, HandshakeStatus, HandshakeReceptionMessage


class ConnectionHandler:
    CONNECTION_PATH: Final[str] = 'vm_connection'
    TIMEOUT_BEFORE_CLOSE: Final[int] = 10
    TIMEOUT_FOR_AGENT_STARTUP: Final[int] = 10
    KEEPALIVE_REFRESH_TIME_IN_SECONDS: Final[float] = 0.5

    def __init__(self, port: int):
        self.stop_event = threading.Event()
        self.loop = asyncio.get_event_loop()
        self.stop = self.loop.run_in_executor(None, self.stop_event.wait)

        self._port = port
        self._process_pool = ProcessPoolExecutor()

        self._initialization_data = None
        self._client = None
        self._agent_process = None

    @property
    def initialization_data(self) -> HandshakeReceptionMessage:
        return self._initialization_data

    async def get_node_join_details(self) -> RegistrationDetails:
        async with aiohttp.ClientSession() as session:
            response = await session.post(url=f'{self.initialization_data.server_url}/api/v1/node_token',
                                          data=self.initialization_data.machine_unique_identification.model_dump_json(),
                                          headers={"Content-Type": "application/json"})
            return RegistrationDetails(**await response.json())

    async def initial_handshake_handler(self, websocket, path):
        while True:
            try:
                data = json.loads(await websocket.recv())
                response = HandshakeReceptionMessage(**data)

                self._initialization_data = response

                await websocket.send(
                    HandshakeResponse(STATUS=HandshakeStatus.INITIALIZING, DESCRIPTION="Initializing k3s",
                                      SECRET_KEY=response.secret_key).model_dump_json())

                initialization_successful = await self.loop.run_in_executor(self._process_pool,
                                                                            EnvironmentInstaller.download_k3s_agent)

                initialization_successful &= await self.loop.run_in_executor(self._process_pool,
                                                                             EnvironmentInstaller.install_tailscale)

                registration_details = await self.get_node_join_details()

                args = ['agent', '--token', registration_details.k8s_token, '--server',
                        f'https://{registration_details.k8s_ip}:{registration_details.k8s_port}', '--node-name',
                        ''.join(random.choices(string.ascii_lowercase, k=16)),
                        '--node-label', f'unique-name={str(hash(self.initialization_data.machine_unique_identification))}',
                        f'--vpn-auth="name=tailscale,joinKey={registration_details.vpn_token},controlServerURL=http://{registration_details.vpn_ip}:{registration_details.vpn_port}"']

                self._agent_process = await asyncio.create_subprocess_exec(
                    EnvironmentInstaller.K3S_BINARY_LOCATION, *args, stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL)

                if self._agent_process.returncode is None:
                    await self.loop.create_task(self.send_periodic_keepalive())

                await asyncio.sleep(ConnectionHandler.TIMEOUT_FOR_AGENT_STARTUP)

                initialization_successful &= self._agent_process.returncode is None

                if not initialization_successful:
                    err_msg = 'Failed to initialize installers.. terminating'
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
                return

            except ConnectionClosed as e:
                return

            except JSONDecodeError as e:
                logging.error(
                    f"Received non-json message.. ignoring")
                return

    async def close_comms(self, websocket):
        await asyncio.sleep(ConnectionHandler.TIMEOUT_BEFORE_CLOSE)
        await websocket.close()
        self.stop_event.set()

    async def run_until_handshake_complete(self):
        async with serve(self.initial_handshake_handler, "0.0.0.0", self._port):
            await self.stop

    async def connect_to_server(self):
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

        with tempfile.TemporaryDirectory() as tmpdir:
            cert_file = (pathlib.Path(tmpdir) / 'cert.pem')
            cert_file.write_bytes(self.initialization_data.secret_key)
            ssl_context.load_verify_locations(cert_file.absolute())
        self._client = await websockets.connect(
            f"wss://{self._initialization_data.ip}:{self._initialization_data.port}/{ConnectionHandler.CONNECTION_PATH}",
            ssl=ssl_context)

    async def send_periodic_keepalive(self):
        while True:
            async with aiohttp.ClientSession() as session:
                await session.put(url=f'{self.initialization_data.server_url}/api/v1/node_keepalive',
                                  json=self.initialization_data.machine_unique_identification.model_dump(),
                                  headers={"Content-Type": "application/json"})
            await asyncio.sleep(ConnectionHandler.KEEPALIVE_REFRESH_TIME_IN_SECONDS)

    def run(self):
        self.loop.run_until_complete(self.run_until_handshake_complete())
        self.loop.run_until_complete(self.connect_to_server())
        print("Connection accepted")

        while True:
            if self._agent_process.returncode is not None:
                self.loop.run_until_complete(self.close_comms(self._client))
                return

            self.loop.run_until_complete(asyncio.sleep(1))
