# app/db/models.py
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import BigInteger, Integer, String, Text, DateTime, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB

class Base(DeclarativeBase):
    pass

class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", index=True)
    ip_hash: Mapped[str] = mapped_column(String(64), index=False)
    ua: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    severity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)