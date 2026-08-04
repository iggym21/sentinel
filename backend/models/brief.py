import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Thesis(str, enum.Enum):
    bullish = "bullish"
    bearish = "bearish"
    neutral = "neutral"


class SuggestedAction(str, enum.Enum):
    buy = "buy"
    sell = "sell"
    hold = "hold"


class Brief(Base):
    __tablename__ = "brief"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker_id: Mapped[int] = mapped_column(ForeignKey("ticker.id"), nullable=False)
    agent_run_id: Mapped[int] = mapped_column(ForeignKey("agent_run.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    thesis: Mapped[Thesis] = mapped_column(Enum(Thesis), nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    diff_from_prior: Mapped[str | None] = mapped_column(String, nullable=True)
    suggested_action: Mapped[SuggestedAction | None] = mapped_column(
        Enum(SuggestedAction), nullable=True
    )

    ticker: Mapped["Ticker"] = relationship(back_populates="briefs")
    # One-directional pointer to the AgentRun that produced this brief. Deliberately
    # not paired via back_populates with AgentRun.brief, which uses the separate
    # brief_id FK (see agent_run.py for the circular-FK rationale).
    agent_run: Mapped["AgentRun"] = relationship(foreign_keys=[agent_run_id])

    @property
    def ticker_symbol(self) -> str:
        """Convenience accessor so `BriefOut`/`BriefDetail` (from_attributes=True)
        can expose the ticker's symbol without every caller needing a manual join."""
        return self.ticker.symbol if self.ticker else "UNKNOWN"
