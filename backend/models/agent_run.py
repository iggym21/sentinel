import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class RunStatus(str, enum.Enum):
    running = "running"
    complete = "complete"
    failed = "failed"


class AgentRun(Base):
    __tablename__ = "agent_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker_id: Mapped[int] = mapped_column(ForeignKey("ticker.id"), nullable=False)
    anomaly_id: Mapped[int | None] = mapped_column(ForeignKey("anomaly.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), nullable=False)
    trace: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # Circular FK with brief: brief.agent_run_id (not null) points back here, so this
    # FK is deferred via use_alter to avoid a table-creation cycle, and set once the
    # run's brief is generated.
    brief_id: Mapped[int | None] = mapped_column(
        ForeignKey("brief.id", use_alter=True, name="fk_agent_run_brief_id"),
        nullable=True,
    )

    ticker: Mapped["Ticker"] = relationship(back_populates="agent_runs")
    anomaly: Mapped["Anomaly"] = relationship(back_populates="agent_run", foreign_keys=[anomaly_id])
    # One-directional pointer to the completed brief. Deliberately not paired via
    # back_populates with Brief.agent_run, which uses the separate agent_run_id FK.
    brief: Mapped["Brief"] = relationship(foreign_keys=[brief_id], uselist=False)
