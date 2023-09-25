from pydantic import BaseModel


class PassThroughMessage(BaseModel):
    TAG: str
    DATA: str
