# app/api/routes_events.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, Query, HTTPException, Request, status
from pydantic import BaseModel, Field, conint, constr
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.events import list_events, daily_counts, top_reason_counts, top_paths
import time, inspect
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
        f = float(s)
        # timezone-aware UTC üret
        return datetime.fromtimestamp(f, tz=timezone.utc)
    except Exception:
        pass
    # ISO
    try:
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(s, fmt)
                # naive ise UTC varsay
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
    except Exception:
        pass
    return None

async def _call_repo(fn, *args, **kwargs):
    """
    Repo fonksiyonu async ise await, sync ise direkt çağır.
    Ayrıca fn imzasında olmayan keyword'leri filtrele.
    """
    try:
        sig = inspect.signature(fn)
        fkwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
    except Exception:
        fkwargs = kwargs
    if inspect.iscoroutinefunction(fn):
        return await fn(*args, **fkwargs)
    return fn(*args, **fkwargs)

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
        # Repo isim farklarını tolere et: client -> ip_hash, ts -> ts|timestamp
        kw = dict(
            client=payload.client,
            ip_hash=payload.client,   # her iki isim de denensin
            kind=payload.kind,
            reason=payload.reason,
            path=payload.path,
            meta=payload.meta or {},
            ts=ts,
            timestamp=ts,
            ua=None,
            score=None,
            severity=None,
        )
        # Şema uyumluluğu: bazı kurulumlarda NOT NULL olabilir
        if kw.get("severity") is None:
            kw["severity"] = 0
        if kw.get("score") is None:
            kw["score"] = 0.0
        if kw.get("ua") is None:
            kw["ua"] = ""
        fn = getattr(repo, "insert_event", None)
        if not fn:
            raise HTTPException(status_code=500, detail="insert_event not available")
        new_id = await _call_repo(fn, session, **kw)
        # Insert'i kalıcı yap
        try:
            await session.commit()
        except Exception as ce:
            await session.rollback()
            raise HTTPException(status_code=500, detail=f"commit failed: {ce}")
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
        # client/ip_hash ve tarih isim farklarını tolere et
        kw = dict(
            limit=int(limit),
            offset=int(offset),
            since=start_ts,
            until=end_ts,
            start_ts=start_ts,
            end_ts=end_ts,
            client=client,
            ip_hash=client,
            kind=kind,
            reason=reason,
            path=path,
        )
        fn = getattr(repo, "list_events", None) or getattr(repo, "search_events", None)
        if not fn:
            raise HTTPException(status_code=500, detail="list_events/search_events not available")
        res = await _call_repo(fn, session, **kw)
        # Hem (total, rows) hem de sadece rows dönen imzaları destekle
        if isinstance(res, tuple) and len(res) == 2:
            total, rows = res
        else:
            rows = res or []
            total = len(rows)
        items = []
        for r in rows:
            try:
                items.append(EventOut.model_validate(getattr(r, "__dict__", r)).model_dump())
            except Exception:
                # dict ya da raw satır olabilir
                items.append(r)
        return {"items": items, "limit": limit, "offset": offset, "count": len(items), "total": int(total)}
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