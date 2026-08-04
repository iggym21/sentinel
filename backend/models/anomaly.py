import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class TriggerType(str, enum.Enum):
    volume_spike = "volume_spike"
    price_move = "price_move"
    news = "news"


class Anomaly(Base):
    __tablename__ = "anomaly"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker_id: Mapped[int] = mapped_column(ForeignKey("ticker.id"), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trigger_type: Mapped[TriggerType] = mapped_column(Enum(TriggerType), nullable=False)
    raw_metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    watchdog_rationale: Mapped[str] = mapped_column(String, nullable=False)
    triggered_analyst_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    ticker: Mapped["Ticker"] = relationship(back_populates="anomalies")
    agent_run: Mapped["AgentRun"] = relationship(back_populates="anomaly", uselist=False)
