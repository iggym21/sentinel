from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from models.agent_run import RunStatus


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
