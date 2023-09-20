import asyncio
import json
import random
import string
from typing import Final
from concurrent.futures import TimeoutError as ConnectionTimeoutError
import websockets

from worker_manager.vm_manager.schema import HandshakeReceptionMessage


class ControllerInitializer:
    VM_STARTUP_TIMEOUT_SECS: Final[int] = 120
    INITIAL_RESPONSE_TIMEOUT_SECS: Final[int] = 5

    def __init__(self, server_ip: str, server_port: int, vm_port: int):
        random.seed()
        self._server_ip = server_ip
        self._server_port = server_port
        self._vm_port = vm_port
        self._secret_key = ControllerInitializer._get_random_string(256)

    @staticmethod
    def _get_random_string(length: int) -> str:
        letters = string.ascii_lowercase
        return ''.join(random.choice(letters) for i in range(length))

    def wait_for_vm_connection(self):
        try:
            connection = await asyncio.wait_for(websockets.connect(f"ws://localhost:{self._vm_port}"),
                                                ControllerInitializer.VM_STARTUP_TIMEOUT_SECS)
            await connection.send(json.dumps(
                HandshakeReceptionMessage(ip=self._server_ip, port=self._server_port, secret_key=self._secret_key)))
            data = await asyncio.wait_for(connection.recv(), ControllerInitializer.INITIAL_RESPONSE_TIMEOUT_SECS)
            print("xd")
        except ConnectionTimeoutError as e:
            raise Exception("Failed to connect to vm")
