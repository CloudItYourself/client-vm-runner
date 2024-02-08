import asyncio
import json
import logging
import pathlib
import ssl
import tempfile
from typing import Final, Optional, Tuple
import websockets
from pydantic import ValidationError
from ciy_backend_libraries.general.sockets import get_ethernet_ip, get_available_port
from ciy_backend_libraries.security.ssl_generation import generate_self_signed_cert
from ciy_backend_libraries.websockets.websocket_server import WebSocketSubscriber, WebSocketServer
from websockets.exceptions import ConnectionClosedOK

from utilities.machine_identification import get_machine_unique_id
from utilities.messages import HandshakeResponse, HandshakeStatus, HandshakeReceptionMessage
from worker_manager import LOGGER_NAME
from worker_manager.configuration.configuration_manager import ConfigurationManager
from worker_manager.vm_manager.qemu_initializer import QemuInitializer


class InternalControllerComms(WebSocketSubscriber):
    TIMEOUT_RETRY_COUNT: Final[int] = 10
    TIMEOUT_BETWEEN_RUNS: Final[int] = 20
    VM_TIMEOUT_BETWEEN_CONNECTIONS_IN_SEC: Final[int] = 2
    INITIAL_RESPONSE_TIMEOUT_SECS: Final[int] = 600
    HELLO_MSG_TIMEOUT_SECS: Final[int] = 5
    CONNECTION_PATH: Final[str] = '/vm_connection'

    def __init__(self, core_count: int, memory_size: int,
                 image_location: str, qemu_installation_location: str):

        self._logger = logging.getLogger(LOGGER_NAME)

        self._qemu_initializer = QemuInitializer(core_count, memory_size, image_location, qemu_installation_location)
        self._server_ip = get_ethernet_ip()
        self._server_port = get_available_port()
        self._cert, self._private_key = generate_self_signed_cert(self._server_ip, self._server_ip)
        self._server_url = ConfigurationManager().config.server_url
        self.loop = asyncio.get_event_loop()
        self._server = self.run_server_in_background()
        self._server.subscribe(InternalControllerComms.CONNECTION_PATH, self)

        self._vm_ready = False
        self._vm_connected = False

        self._machine_details = get_machine_unique_id()
        self._vm_port = get_available_port()
        self._qemu_initializer.run_vm(self._vm_port)
        self.loop.run_until_complete(self.wait_for_vm_connection())
        self._current_vm_sid: Optional[str] = None
        self._lock = asyncio.Lock()
        self._should_terminate = False

    @property
    def should_terminate(self):
        return self._should_terminate

    def get_vm_usage(self, interval: int) -> Tuple[float, float, float, float]:
        return self._qemu_initializer.get_vm_utilization(interval)

    async def wait_for_initial_connection(self):
        exception = None
        for i in range(InternalControllerComms.TIMEOUT_RETRY_COUNT):
            try:
                connection = await websockets.connect(f"ws://127.0.0.1:{self._vm_port}",
                                                      timeout=InternalControllerComms.TIMEOUT_BETWEEN_RUNS)
                return connection
            except Exception as e:
                exception = e
                await asyncio.sleep(InternalControllerComms.VM_TIMEOUT_BETWEEN_CONNECTIONS_IN_SEC)
        raise exception

    async def wait_for_vm_connection(self):
        connection = None
        try:
            self._logger.info("Waiting for initial connection from VM")
            connection = await self.wait_for_initial_connection()
            self._logger.info("VM connected, sending handshake")
            await connection.send(HandshakeReceptionMessage(ip=self._server_ip, port=self._server_port,
                                                            secret_key=self._cert, server_url=self._server_url,
                                                            machine_unique_identification=self._machine_details).model_dump_json())
            connection_complete = False
            first_msg = True
            while not connection_complete:
                if first_msg:
                    self._logger.info("Waiting for initial response")
                    raw_data = await asyncio.wait_for(connection.recv(),
                                                      InternalControllerComms.INITIAL_RESPONSE_TIMEOUT_SECS)
                    self._logger.info("Initial response received")
                    first_msg = False
                else:
                    raw_data = await connection.recv()
                data = json.loads(raw_data)
                try:
                    response = HandshakeResponse(**data)
                    self._logger.info(
                        f"Received handshake with status: {response.STATUS}, description: {response.DESCRIPTION}")
                    if response.STATUS == HandshakeStatus.FAILURE:
                        self._logger.error(f"Initialization error: {data}, terminating")
                        raise Exception(f"Initialization error: {data}")
                    elif response.STATUS == HandshakeStatus.SUCCESS:
                        self._logger.info(f"Handshake successful, vm is ready")

                        connection_complete = True
                        self._vm_ready = True

                except ValidationError as e:
                    self._logger.info(f"Failed to parse verify data: {data}")
                    raise Exception(f"Failed to parse verify data: {data}")
                except ConnectionClosedOK as e:
                    self._logger.info(f"VM initial connection closed")
                    return

        except TimeoutError as e:
            raise Exception("Failed to connect to vm")
        finally:
            if connection is not None:
                await connection.close()

    async def wait_for_full_vm_connection(self):
        while not self._vm_connected:
            await asyncio.sleep(1)

    async def handle_connect(self, sid: str):
        if self._vm_connected and self._vm_ready:
            await self._server.force_disconnect(sid)
        else:
            self._logger.info("Vm connected to websocket interface")
            self._current_vm_sid = sid
            self._vm_connected = True

    async def handle_disconnect(self, sid: str):
        if self._vm_connected and sid == self._current_vm_sid:
            self._vm_connected = False
            self._logger.error("Vm disconnected from websocket interface")
            self._should_terminate = True

    def run_server_in_background(self):
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_default_certs()
        with tempfile.TemporaryDirectory() as tmpdir:
            cert_file = (pathlib.Path(tmpdir) / 'cert.pem')
            cert_file.write_bytes(self._cert)
            key_file = (pathlib.Path(tmpdir) / 'key.pem')
            key_file.write_bytes(self._private_key)

            ssl_context.load_cert_chain(certfile=cert_file.absolute(), keyfile=key_file.absolute())
        self._logger.info(f"Running raw websocket server on wss://{self._server_ip}:{self._server_port}")
        return WebSocketServer(self._server_ip, self._server_port, ssl_context=ssl_context)

    def terminate(self):
        self._qemu_initializer.kill_vm()
