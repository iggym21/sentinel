from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TickerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    added_at: datetime
    active: bool


class TickerCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    active: bool = True
