# app/api/routes_events.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, Query, HTTPException, Request, status
from pydantic import BaseModel, Field, conint, constr
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.events import list_events, daily_counts, top_reason_counts, top_paths
import time
import app.repositories.events as repo  # module import for insert/search helpers

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

# --- Yeni ingest/search modelleri ---
_Str32 = constr(strip_whitespace=True, min_length=1, max_length=32)
_Str64 = constr(strip_whitespace=True, min_length=1, max_length=64)
_Str256 = constr(strip_whitespace=True, min_length=1, max_length=256)

class EventIn(BaseModel):
    client: _Str64
    kind: _Str32
    reason: _Str64
    path: _Str256
    meta: Optional[dict] = None
    ts: Optional[float] = Field(None, description="Unix epoch seconds; boş ise server now()")

class OkCreated(BaseModel):
    ok: bool = True
    id: Optional[int] = None

def _parse_ts(s: Optional[str]):
    """float epoch ya da ISO (YYYY-MM-DD[THH:MM:SS]) -> datetime | None"""
    if not s:
        return None
    # float epoch
    try:
        from datetime import datetime
        f = float(s)
        return datetime.fromtimestamp(f)
    except Exception:
        pass
    # ISO
    try:
        from datetime import datetime
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
    except Exception:
        pass
    return None

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


# --- Yeni ingest/search uçları ---

@router.post("", response_model=OkCreated, status_code=status.HTTP_201_CREATED)
async def create_event(payload: EventIn, session: AsyncSession = Depends(get_session)):
    """
    Yeni olay ingest ucu. Var olan GET /events'i bozmaz; aynı path'e POST.
    """
    # repo.insert_event bekleniyor; yoksa 500 döner
    if not hasattr(repo, "insert_event"):
        raise HTTPException(status_code=500, detail="insert_event() not available")
    ts = float(payload.ts or time.time())
    try:
        new_id = await repo.insert_event(
            session,
            client=payload.client,
            kind=payload.kind,
            reason=payload.reason,
            path=payload.path,
            meta=payload.meta or {},
            ts=ts,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"insert failed: {e}")
    return OkCreated(ok=True, id=int(new_id) if isinstance(new_id, int) else None)


@router.get("/search")
async def search_events(
    request: Request,
    limit: conint(ge=1, le=1000) = 100,
    offset: conint(ge=0) = 0,
    since: Optional[str] = None,
    until: Optional[str] = None,
    client: Optional[str] = None,
    kind: Optional[str] = None,  # şimdilik repo desteklemiyorsa yok sayılır
    reason: Optional[str] = None,
    path: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Gelişmiş arama. Mevcut list_events() imzasına uyacak şekilde map eder.
    """
    try:
        start_ts = _parse_ts(since)
        end_ts = _parse_ts(until)
        ip_hash = client  # client -> ip_hash
        total, rows = await list_events(
            session,
            start_ts=start_ts,
            end_ts=end_ts,
            reason=reason,
            path=path,
            ip_hash=ip_hash,
            limit=limit,
            offset=offset,
        )
        items = [EventOut.model_validate(r.__dict__).model_dump() for r in rows]
        return {"items": items, "limit": limit, "offset": offset, "count": len(items), "total": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"search failed: {e}")

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