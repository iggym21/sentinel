from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Ticker(Base):
    __tablename__ = "ticker"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(
        back_populates="ticker"
    )
    anomalies: Mapped[list["Anomaly"]] = relationship(back_populates="ticker")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="ticker")
    briefs: Mapped[list["Brief"]] = relationship(back_populates="ticker")
