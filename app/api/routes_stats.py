from __future__ import annotations

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.persistence.db import get_session
from app.persistence.repo import daily_summary, retention_purge
from app.core.settings import get_settings

from typing import Optional

try:
    from app.repositories import events as repo
    from app.db import get_db
except Exception as _e:  # pragma: no cover
    repo = None  # type: ignore
    get_db = None  # type: ignore


router = APIRouter(prefix="/stats", tags=["stats"])
_settings = get_settings()

router_admin = APIRouter(prefix="/_admin/stats", tags=["stats"])

def _parse_ts(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        pass
    try:
        from datetime import datetime
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(s, fmt).timestamp()
            except Exception:
                continue
    except Exception:
        pass
    return None

# Basit admin guard: local/dev için X-Debug-Admin: 1
async def require_admin(request: Request):
    if request.headers.get("X-Debug-Admin") == "1":
        return True
    raise HTTPException(status_code=403, detail="admin only")

@router.get("/daily_summary")
async def get_daily_summary(session: AsyncSession = Depends(get_session)):
    return await daily_summary(session)

@router.post("/purge")
async def purge_retention(days: int = Query(default=None, ge=1, le=365), session: AsyncSession = Depends(get_session)):
    d = days if days is not None else _settings.RETENTION_DAYS
    await retention_purge(session, d)
    return {"ok": True, "purged_older_than_days": d}


# --- Admin endpoints ---

@router_admin.get("/top-reasons", dependencies=[Depends(require_admin)])
async def top_reasons(limit: int = 10, since: Optional[str] = None, until: Optional[str] = None, db=Depends(get_db)):
    if repo is None or get_db is None:
        raise HTTPException(status_code=500, detail="Repository/DB not wired")
    try:
        rows = repo.top_reason_counts(
            db,
            limit=max(1, min(int(limit), 1000)),
            since=_parse_ts(since),
            until=_parse_ts(until),
        )
        return {"items": rows}
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"top_reasons failed: {e}")


@router_admin.get("/top-paths", dependencies=[Depends(require_admin)])
async def top_paths(limit: int = 10, since: Optional[str] = None, until: Optional[str] = None, db=Depends(get_db)):
    if repo is None or get_db is None:
        raise HTTPException(status_code=500, detail="Repository/DB not wired")
    try:
        rows = repo.top_paths(
            db,
            limit=max(1, min(int(limit), 1000)),
            since=_parse_ts(since),
            until=_parse_ts(until),
        )
        return {"items": rows}
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"top_paths failed: {e}")