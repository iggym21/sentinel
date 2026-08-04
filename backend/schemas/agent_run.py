from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer

from models.agent_run import RunStatus
from schemas.ticker import utc_iso


class AgentRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker_id: int
    anomaly_id: int | None
    started_at: datetime
    completed_at: datetime | None
    status: RunStatus
    trace: list[dict[str, Any]]
    brief_id: int | None

    @field_serializer("started_at", "completed_at", when_used="json")
    def _serialize_timestamps(self, dt: datetime | None) -> str | None:
        return utc_iso(dt)
