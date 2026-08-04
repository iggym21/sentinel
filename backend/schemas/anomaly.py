from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer

from models.anomaly import TriggerType
from schemas.ticker import utc_iso


class AnomalyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker_id: int
    detected_at: datetime
    trigger_type: TriggerType
    raw_metrics: dict[str, Any]
    watchdog_rationale: str
    triggered_analyst_run: bool

    @field_serializer("detected_at", when_used="json")
    def _serialize_detected_at(self, dt: datetime) -> str | None:
        return utc_iso(dt)
