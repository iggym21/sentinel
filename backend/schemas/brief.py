from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from models.brief import SuggestedAction, Thesis
from schemas.agent_run import AgentRunOut


class BriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker_id: int
    agent_run_id: int
    created_at: datetime
    thesis: Thesis
    confidence: int
    summary: str
    evidence: list[dict[str, Any]]
    diff_from_prior: str | None
    suggested_action: SuggestedAction | None


class BriefDetail(BriefOut):
    """`BriefOut` merged with the full `AgentRun` (including its reasoning trace)."""

    agent_run: AgentRunOut
