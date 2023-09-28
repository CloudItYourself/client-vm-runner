from pydantic import BaseModel


class HandshakeReceptionMessage(BaseModel):
    ip: str
    port: int
    secret_key: bytes
