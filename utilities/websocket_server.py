import asyncio
import ssl
import threading
from abc import abstractmethod
from typing import List, Any, Dict

from websockets.exceptions import ConnectionClosed
from websockets.server import serve


class WebSocketSubscriber:
    @abstractmethod
    async def handle_connect(self, sid: str):
        pass

    @abstractmethod
    async def handle_disconnect(self, sid: str):
        pass


class WebSocketServer:
    def __init__(self, ip_to_bind: str, port: int, ssl_context: ssl.SSLContext = None):
        self.stop_event = threading.Event()
        self.loop = asyncio.get_event_loop()
        self.stop = self.loop.run_in_executor(None, self.stop_event.wait)
        self._ip_to_bind = ip_to_bind
        self._port = port
        if ssl_context is not None:
            self._server = self.loop.run_until_complete(
                serve(self.general_handler, self._ip_to_bind, self._port, ssl=ssl_context))
        else:
            self._server = self.loop.run_until_complete(serve(self.general_handler, self._ip_to_bind, self._port))
        self._path_to_subscribers: Dict[str, WebSocketSubscriber] = {}
        self._websocket_id_to_websocket = {}

    async def stop(self):
        await self._server.ws_server.close()
        self.stop_event.set()

    def subscribe(self, path: str, subscriber: WebSocketSubscriber):
        self._path_to_subscribers[path] = subscriber

    async def send_message(self, websocket_id: str, message, wait_for_response: bool = False):
        if websocket_id in self._websocket_id_to_websocket:
            await self._websocket_id_to_websocket[websocket_id].send(message)
            if wait_for_response:
                return await self._websocket_id_to_websocket[websocket_id].recv()

    async def force_disconnect(self, websocket_id: str):
        if websocket_id in self._websocket_id_to_websocket:
            await self._websocket_id_to_websocket[websocket_id].close()

    async def general_handler(self, websocket, path):
        self._websocket_id_to_websocket[websocket.id] = websocket
        if path in self._path_to_subscribers:
            await self._path_to_subscribers[path].handle_connect(websocket.id)
            while True:
                try:
                    await asyncio.sleep(1000)
                except ConnectionClosed:
                    await self._path_to_subscribers[path].handle_disconnect(websocket.id)
