from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer

from models.brief import SuggestedAction, Thesis
from schemas.agent_run import AgentRunOut
from schemas.ticker import utc_iso


class BriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker_id: int
    ticker_symbol: str
    agent_run_id: int
    created_at: datetime
    thesis: Thesis
    confidence: int
    summary: str
    evidence: list[dict[str, Any]]
    diff_from_prior: str | None
    suggested_action: SuggestedAction | None

    @field_serializer("created_at", when_used="json")
    def _serialize_created_at(self, dt: datetime) -> str | None:
        return utc_iso(dt)


class BriefDetail(BriefOut):
    """`BriefOut` merged with the full `AgentRun` (including its reasoning trace)."""

    agent_run: AgentRunOut
