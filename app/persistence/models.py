from sqlalchemy import BigInteger, Column, Integer, Text, JSON, Index, Float
from sqlalchemy.dialects.postgresql import TIMESTAMP as PgTimestamp
from sqlalchemy.orm import Mapped, mapped_column
from app.persistence.db import Base

class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[str] = mapped_column(PgTimestamp(timezone=True), nullable=False)
    ip_hash: Mapped[str] = mapped_column(Text, nullable=False)
    ua: Mapped[str] = mapped_column(Text, nullable=True)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)  # e.g. path_scan, rate_abuse, z_anomaly
    score: Mapped[float | None] = mapped_column(Float, nullable=True)  # z-score or similar
    severity: Mapped[int] = mapped_column(Integer, default=0)  # 0..3
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

Index("ix_events_ts", Event.ts)
Index("ix_events_ip_ts", Event.ip_hash, Event.ts)
Index("ix_events_reason", Event.reason)