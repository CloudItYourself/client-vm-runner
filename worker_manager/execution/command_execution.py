import websockets


class CommandExecution:
    def __init__(self, server_ip: str, server_port: int, path: str):
        self._server_ip = server_ip
        self._server_port = server_port
        self._path = path
        self._client = None

    async def initialize(self):
        self._client = await websockets.connect(f"ws://{self._server_ip}:{self._server_port}/{self._path}")

    def wait_for_command(self):
        pass