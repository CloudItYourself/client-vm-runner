import asyncio
import json
import logging
import pathlib
import random
import string
from typing import Final, Dict
import websockets
from aiohttp import web
from pydantic import ValidationError
from websockets.exceptions import ConnectionClosedOK

from internal_controller.connection.schema import HandshakeResponse, HandshakeStatus
from utilities.sockets import get_available_port
from worker_manager.vm_manager.qemu_initializer import QemuInitializer
from worker_manager.vm_manager.schema import HandshakeReceptionMessage
import socketio


class InternalControllerComms(socketio.AsyncNamespace):
    VM_STARTUP_TIMEOUT_SECS: Final[int] = 120
    INITIAL_RESPONSE_TIMEOUT_SECS: Final[int] = 5
    NAMESPACE: Final[str] = '/vm_connection'

    def __init__(self, core_count: int, memory_size: int,
                 image_location=pathlib.Path(r"E:\FreeCloudProject\worker_manager\image_builder\staging\linux.img")):
        super().__init__(InternalControllerComms.NAMESPACE)

        random.seed()
        self._qemu_initializer = QemuInitializer(core_count, memory_size, image_location)
        self._server_ip = "127.0.0.1"
        self._server_port = get_available_port()
        self._secret_key = InternalControllerComms._get_random_string(256)

        self.loop = asyncio.get_event_loop()
        self.loop.create_task(self.run_server_in_background())

        self._vm_ready = False
        self._vm_connected = False

        self._vm_port = get_available_port()
        self._qemu_initializer.run_vm(self._vm_port)
        self.loop.run_until_complete(self.wait_for_vm_connection())

    @staticmethod
    def _get_random_string(length: int) -> str:
        letters = string.ascii_lowercase
        return ''.join(random.choice(letters) for i in range(length))

    async def wait_for_vm_connection(self):
        try:
            await asyncio.sleep(InternalControllerComms.VM_STARTUP_TIMEOUT_SECS)  # allow for startup to occur
            connection = await websockets.connect(f"ws://127.0.0.1:{self._vm_port}",
                                                  timeout=InternalControllerComms.VM_STARTUP_TIMEOUT_SECS)
            await connection.send(HandshakeReceptionMessage(ip=self._server_ip, port=self._server_port,
                                                            secret_key=self._secret_key).model_dump_json())
            connection_complete = False
            while not connection_complete:
                data = json.loads(await asyncio.wait_for(connection.recv(), InternalControllerComms.INITIAL_RESPONSE_TIMEOUT_SECS))
                try:
                    response = HandshakeResponse(**data)
                    if response.SECRET_KEY != self._secret_key:
                        raise Exception(f"Secret key does not match!! Major error")
                    elif response.STATUS == HandshakeStatus.FAILURE:
                        raise Exception(f"Initialization error: {data}")
                    elif response.STATUS == HandshakeStatus.SUCCESS:
                        connection_complete = True
                        self._vm_ready = True

                except ValidationError as e:
                    raise Exception(f"Failed to parse veirfy data: {data}")
                except ConnectionClosedOK as e:
                    pass
                finally:
                    await connection.close()

        except TimeoutError as e:
            raise Exception("Failed to connect to vm")

    async def on_connect(self, sid: str, environ: Dict[str, str]):
        if self._vm_connected and self._vm_ready:
            await self.disconnect(sid)
        else:
            logging.info("Vm connected!!")
            self._vm_connected = True

    async def on_disconnect(self, sid: str):
        if self._vm_connected:
            self._vm_connected = False

    async def run_server_in_background(self):
        sio = socketio.AsyncServer(async_mode='aiohttp', logger=True, engineio_logger=True)
        sio.register_namespace(self)
        app = web.Application()
        sio.attach(app)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host=self._server_ip, port=self._server_port)
        await site.start()


if __name__ == '__main__':
    xd = InternalControllerComms(core_count=4, memory_size=4000)
    while True:
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(5))
        print(xd._vm_connected)
