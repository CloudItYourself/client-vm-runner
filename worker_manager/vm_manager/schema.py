from typing import TypedDict


class HandshakeReceptionMessage(TypedDict):
    ip: str
    port: int
    secret_key: str
