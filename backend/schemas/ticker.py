import re
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

# Real ticker symbols: 1-10 chars, start with a letter, and otherwise only
# letters/digits/`.`/`-` (e.g. "BRK.B", "RDS-A") — deliberately excludes
# anything that could reshape a URL path an outbound HTTP client builds
# from this value (e.g. "/", "?", ".."), since AlpacaProvider/EdgarProvider
# interpolate the ticker straight into request paths.
SYMBOL_PATTERN = r"^[A-Z][A-Z0-9.\-]{0,9}$"
_SYMBOL_RE = re.compile(SYMBOL_PATTERN)


def normalize_symbol(symbol: str) -> str:
    """Normalize (strip + uppercase) and validate a path-param ticker
    symbol, raising `HTTPException(422)` if it doesn't match the same
    pattern `TickerCreate.symbol` enforces on the request body. FastAPI
    path params are plain `str` — they don't run through a Pydantic model,
    so routes taking a `{symbol}` path param must call this explicitly."""
    normalized = symbol.strip().upper()
    if not _SYMBOL_RE.fullmatch(normalized):
        raise HTTPException(status_code=422, detail=f"Invalid ticker symbol: {symbol!r}")
    return normalized


def utc_iso(dt: datetime | None) -> str | None:
    """Serialize a datetime with an explicit UTC offset. SQLite drops
    `tzinfo` on round-trip even though every write in this app is
    `datetime.now(timezone.utc)`, so a naive value read back out is
    always UTC in practice — mirrors `api/watchlist.py`'s `_as_utc()`
    but applied at the wire-serialization boundary instead of for
    internal comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class TickerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    added_at: datetime
    active: bool

    @field_serializer("added_at", when_used="json")
    def _serialize_added_at(self, dt: datetime) -> str | None:
        return utc_iso(dt)


class TickerCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str = Field(pattern=SYMBOL_PATTERN)
    active: bool = True

    @field_validator("symbol", mode="before")
    @classmethod
    def _normalize_symbol(cls, v: object) -> object:
        # Runs before the `Field(pattern=...)` constraint is checked, so a
        # lowercase "aapl" from a client is normalized to "AAPL" first and
        # still validates.
        if isinstance(v, str):
            return v.strip().upper()
        return v


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

    @field_serializer("added_at", "last_brief_at", when_used="json")
    def _serialize_timestamps(self, dt: datetime | None) -> str | None:
        return utc_iso(dt)
