import asyncio
import json
import logging
import pathlib
import ssl
import tempfile
from typing import Final, Optional
import websockets
from pydantic import ValidationError
from websockets.exceptions import ConnectionClosedOK

from utilities.messages import HandshakeResponse, HandshakeStatus, HandshakeReceptionMessage, ExecutionResponse, \
    ExecutionRequest
from utilities.certificates import generate_self_signed_cert
from utilities.sockets import get_available_port, get_ethernet_ip
from utilities.websocket_server import WebSocketSubscriber, WebSocketServer
from worker_manager.vm_manager.qemu_initializer import QemuInitializer


class InternalControllerComms(WebSocketSubscriber):
    TIMEOUT_RETRY_COUNT: Final[int] = 10
    TIMEOUT_BETWEEN_RUNS: Final[int] = 10
    VM_TIMEOUT_BETWEEN_CONNECTIONS_IN_SEC: Final[int] = 2
    INITIAL_RESPONSE_TIMEOUT_SECS: Final[int] = 180
    HELLO_MSG_TIMEOUT_SECS: Final[int] = 5
    CONNECTION_PATH: Final[str] = '/vm_connection'

    def __init__(self, core_count: int, memory_size: int,
                 image_location: str, qemu_installation_location: str):
        self._qemu_initializer = QemuInitializer(core_count, memory_size, image_location, qemu_installation_location)
        self._server_ip = get_ethernet_ip()
        self._server_port = get_available_port()
        self._cert, self._private_key = generate_self_signed_cert(self._server_ip, self._server_ip)

        self.loop = asyncio.get_event_loop()
        self._server = self.run_server_in_background()
        self._server.subscribe(InternalControllerComms.CONNECTION_PATH, self)

        self._vm_ready = False
        self._vm_connected = False

        self._vm_port = get_available_port()
        # self._vm_port = 39019
        self._qemu_initializer.run_vm(self._vm_port)
        self.loop.run_until_complete(self.wait_for_vm_connection())
        self._current_vm_sid: Optional[str] = None
        self._lock = asyncio.Lock()
        self._current_job_id = 0
        self._should_terminate = False

    @property
    def should_terminate(self):
        return self._should_terminate

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
            connection = await self.wait_for_initial_connection()
            logging.info("Accepted connection from internal vm process")
            await connection.send(HandshakeReceptionMessage(ip=self._server_ip, port=self._server_port,
                                                            secret_key=self._cert).model_dump_json())
            logging.info("Sent handshake details")
            connection_complete = False
            first_msg = True
            while not connection_complete:
                if first_msg:
                    raw_data = await asyncio.wait_for(connection.recv(),
                                                      InternalControllerComms.INITIAL_RESPONSE_TIMEOUT_SECS)
                    first_msg = False
                else:
                    raw_data = await connection.recv()
                data = json.loads(raw_data)
                try:
                    response = HandshakeResponse(**data)
                    logging.info(
                        f"Received handshake with status: {response.STATUS}, description: {response.DESCRIPTION}")
                    if response.STATUS == HandshakeStatus.FAILURE:
                        raise Exception(f"Initialization error: {data}")
                    elif response.STATUS == HandshakeStatus.SUCCESS:
                        connection_complete = True
                        self._vm_ready = True

                except ValidationError as e:
                    raise Exception(f"Failed to parse verify data: {data}")
                except ConnectionClosedOK as e:
                    return

        except TimeoutError as e:
            raise Exception("Failed to connect to vm")
        finally:
            if connection is not None:
                await connection.close()

    async def handle_connect(self, sid: str):
        if self._vm_connected and self._vm_ready:
            await self._server.force_disconnect(sid)
        else:
            logging.info("Vm connected")
            self._current_vm_sid = sid
            self._vm_connected = True

    async def handle_disconnect(self, sid: str):
        if self._vm_connected and sid == self._current_vm_sid:
            self._vm_connected = False
            logging.info("Vm disconnected")
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

        return WebSocketServer(self._server_ip, self._server_port, ssl_context=ssl_context)

    async def send_request(self, request: ExecutionRequest):
        async with self._lock:
            return await self._server.send_message(self._current_vm_sid, request.model_dump_json(),
                                                   wait_for_response=True)

    def terminate(self):
        self._qemu_initializer.kill_vm()
