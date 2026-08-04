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


class WatchlistEntry(BaseModel):
    """`TickerOut` plus computed fields for the `/api/watchlist` list view."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    added_at: datetime
    active: bool
    latest_price: float | None
    day_change_pct: float | None
    status: str
    last_brief_at: datetime | None
