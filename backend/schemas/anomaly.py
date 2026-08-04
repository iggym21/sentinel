from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from models.anomaly import TriggerType


class AnomalyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker_id: int
    detected_at: datetime
    trigger_type: TriggerType
    raw_metrics: dict[str, Any]
    watchdog_rationale: str
    triggered_analyst_run: bool
