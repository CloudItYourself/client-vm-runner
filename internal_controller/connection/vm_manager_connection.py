import asyncio
import json
import logging
import os
import pathlib
import random
import ssl
import string
import tempfile
import threading

import requests
import websockets
from ciy_backend_libraries.api.cluster_access.v1.node_registrar import RegistrationDetails, NodeDetails

from internal_controller import LOGGER_NAME
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
    TIMEOUT_BETWEEN_NODE_CHECKS: Final[int] = 2
    NODE_CHECK_INITIAL_TIMEOUT: Final[int] = 300
    KEEPALIVE_REFRESH_TIME_IN_SECONDS: Final[float] = 0.5
    TAILSCALE_JOIN_DETAILS_FILE_NAME: Final[str] = 'tailscale_params.txt'

    def __init__(self, port: int):
        self.stop_event = threading.Event()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._logger = logging.getLogger(LOGGER_NAME)
        self.stop = self.loop.run_in_executor(None, self.stop_event.wait)
        self._node_name = ''.join(random.choices(string.ascii_lowercase, k=16))
        self._port = port
        self._process_pool = ProcessPoolExecutor()
        self._background_keepalive_task = None
        self._initialization_data = None
        self._client = None
        self._http_lock = asyncio.Lock()

    async def connect_to_server(self):
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

        with tempfile.TemporaryDirectory() as tmpdir:
            cert_file = (pathlib.Path(tmpdir) / 'cert.pem')
            cert_file.write_bytes(self.initialization_data.secret_key)
            ssl_context.load_verify_locations(cert_file.absolute())
        self._client = await websockets.connect(
            f"wss://{self._initialization_data.ip}:{self._initialization_data.port}/{ConnectionHandler.CONNECTION_PATH}",
            ssl=ssl_context)

    @property
    def initialization_data(self) -> HandshakeReceptionMessage:
        return self._initialization_data

    @staticmethod
    def send_post_request(url: str, details: NodeDetails):
        return requests.post(url=f'{url}/api/v1/node_token',
                             data=details.model_dump_json(),
                             headers={"Content-Type": "application/json"}).json()

    async def get_node_join_details(self) -> RegistrationDetails:
        response = await self.loop.run_in_executor(None, ConnectionHandler.send_post_request,
                                                   self.initialization_data.server_url,
                                                   self.initialization_data.machine_unique_identification)
        return RegistrationDetails(**response)

    @staticmethod
    def run_k3s_agent_in_background(node_name: str, registration_details: RegistrationDetails) -> bool:
        os.environ['INVOCATION_ID'] = ""
        k3s_uninstall = pathlib.Path('/usr/local/bin/k3s-agent-uninstall.sh')
        if k3s_uninstall.exists():
            k3s_path = pathlib.Path('/usr/local/bin/k3s')

            k3s_temp_path = pathlib.Path('/usr/local/bin/k3s_temp')
            k3s_temp_path.write_bytes(k3s_path.read_bytes())

            os.system('/usr/local/bin/k3s-agent-uninstall.sh')

            k3s_path.write_bytes(k3s_temp_path.read_bytes())
            k3s_temp_path.unlink()
            k3s_path.chmod(0o777)

        agent_installation_command = (
            f'INSTALL_K3S_SKIP_START=true INSTALL_K3S_SKIP_DOWNLOAD=true INSTALL_K3S_EXEC="agent --token {registration_details.k8s_token}'
            f' --server https://{registration_details.k8s_ip}:{registration_details.k8s_port}'
            f' --node-name {node_name} --kubelet-arg cgroups-per-qos=false --kubelet-arg enforce-node-allocatable='
            f' --vpn-auth="name=tailscale,joinKey={registration_details.vpn_token},controlServerURL=https://{registration_details.vpn_ip}:{registration_details.vpn_port}"" /usr/local/src/install.sh')

        success_status = os.system(agent_installation_command) == 0
        k3s_env_file = pathlib.Path("/etc/systemd/system/k3s-agent.service.env")
        k3s_env_file.write_text("INVOCATION_ID= \n")
        k3s_env_file.chmod(0o777)
        return success_status and os.system('systemctl start k3s-agent') == 0

    async def initial_handshake_handler(self, websocket, path):
        while True:
            try:
                data = json.loads(await websocket.recv())
                response = HandshakeReceptionMessage(**data)

                self._initialization_data = response

                await websocket.send(
                    HandshakeResponse(STATUS=HandshakeStatus.INITIALIZING, DESCRIPTION="Initializing k3s",
                                      SECRET_KEY=response.secret_key).model_dump_json())

                self._logger.info("Initializing tailscale")
                initialization_successful = await self.loop.run_in_executor(self._process_pool,
                                                                            EnvironmentInstaller.install_tailscale)
                self._logger.info(
                    f"Initializing tailscale with status: {'success' if initialization_successful else 'failure'}")
                registration_details = await self.get_node_join_details()

                self._logger.info(f"Node registration details received.. writing VPN details to file")

                self._background_keepalive_task = self.loop.create_task(
                    self.send_periodic_keepalive())  # start periodic keepalive

                logging.info(f"Running k3s agent...")
                script_installation_res = await self.loop.run_in_executor(self._process_pool,
                                                                          ConnectionHandler.run_k3s_agent_in_background,
                                                                          self._node_name, registration_details)

                initialization_successful = script_installation_res and await self.check_for_node_connection()

                if not initialization_successful:
                    err_msg = 'Failed to initialize installers.. terminating'
                    self._logger.error(err_msg)
                    await websocket.send(
                        HandshakeResponse(STATUS=HandshakeStatus.FAILURE, DESCRIPTION=err_msg).model_dump_json())
                    await self.close_comms(websocket)
                    raise Exception(err_msg)

                await websocket.send(
                    HandshakeResponse(STATUS=HandshakeStatus.SUCCESS, DESCRIPTION="Agent is running").model_dump_json())
                await self.close_comms(websocket)
                return

            except ValidationError as e:
                self._logger.error(
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

    async def check_for_node_connection(self, timeout_in_seconds=NODE_CHECK_INITIAL_TIMEOUT):
        for i in range(int(timeout_in_seconds / ConnectionHandler.TIMEOUT_BETWEEN_NODE_CHECKS)):
            if await self.is_node_online():
                return True
            await asyncio.sleep(ConnectionHandler.TIMEOUT_BETWEEN_NODE_CHECKS)
        return False

    async def send_periodic_keepalive(self):
        while True:
            try:
                async with self._http_lock:
                    await self.loop.run_in_executor(None, requests.put,
                                                    f'{self.initialization_data.server_url}/api/v1/node_keepalive/{self._node_name}')
            except Exception as e:
                self._logger.exception(f"Failed to send keepalive...: {e}")
            await asyncio.sleep(ConnectionHandler.KEEPALIVE_REFRESH_TIME_IN_SECONDS)

    async def is_node_online(self) -> bool:
        try:
            async with self._http_lock:
                url = f'{self.initialization_data.server_url}/api/v1/node_exists/{self._node_name}'
                result: requests.Response = await self.loop.run_in_executor(None, requests.get, url)
                return result.status_code == 200

        except Exception as e:
            self._logger.exception(f"Failed to send node_exists...: {e}")
            return False

    async def main_loop(self):
        await self.run_until_handshake_complete()
        await self.connect_to_server()
        self._logger.info("Connection accepted")

        while True:
            if await self.check_for_node_connection(10) is False:
                self._logger.error("Exiting.. node not online")
                return

            await asyncio.sleep(1)

    def run(self):
        self.loop.run_until_complete(self.main_loop())
