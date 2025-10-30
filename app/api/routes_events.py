# app/api/routes_events.py
from datetime import datetime
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.events import list_events, daily_counts, top_reason_counts, top_paths

router = APIRouter(prefix="/events", tags=["events"])

class EventOut(BaseModel):
    id: int
    ts: datetime
    ip_hash: str
    ua: Optional[str] = None
    path: Optional[str] = None
    reason: Optional[str] = None
    score: Optional[float] = None
    severity: Optional[int] = None
    meta: Optional[dict] = None

class EventsPage(BaseModel):
    total: int
    items: List[EventOut]

@router.get("", response_model=EventsPage)
async def get_events(
    start_ts: Optional[datetime] = Query(None),
    end_ts: Optional[datetime] = Query(None),
    reason: Optional[str] = Query(None),
    path: Optional[str] = Query(None),
    ip_hash: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    total, rows = await list_events(
        session,
        start_ts=start_ts, end_ts=end_ts, reason=reason, path=path, ip_hash=ip_hash,
        limit=limit, offset=offset
    )
    items = [EventOut.model_validate(r.__dict__) for r in rows]
    return EventsPage(total=total, items=items)

stats_router = APIRouter(prefix="/stats", tags=["stats"])

class KeyCount(BaseModel):
    key: Any = Field(..., description="day/reason/path")
    cnt: int

@stats_router.get("/daily", response_model=List[KeyCount])
async def stats_daily(days: int = Query(7, ge=1, le=90), session: AsyncSession = Depends(get_session)):
    rows = await daily_counts(session, days=days)
    return [{"key": r.day, "cnt": r.cnt} for r in rows]

@stats_router.get("/reasons", response_model=List[KeyCount])
async def stats_reasons(limit: int = Query(10, ge=1, le=100), session: AsyncSession = Depends(get_session)):
    rows = await top_reason_counts(session, limit=limit)
    return [{"key": r.reason, "cnt": r.cnt} for r in rows]

@stats_router.get("/paths", response_model=List[KeyCount])
async def stats_paths(limit: int = Query(10, ge=1, le=100), session: AsyncSession = Depends(get_session)):
    rows = await top_paths(session, limit=limit)
    return [{"key": r.path, "cnt": r.cnt} for r in rows]