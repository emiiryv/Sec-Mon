from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.persistence.db import get_session
from app.persistence.repo import query_events

router = APIRouter(prefix="/events", tags=["events"])

@router.get("")
async def get_events(
    ip_hash: str | None = Query(default=None),
    reason: str | None = Query(default=None),
    since_iso: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
):
    since = None
    if since_iso:
        since = datetime.fromisoformat(since_iso)
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
    return await query_events(session, ip_hash=ip_hash, reason=reason, since=since, limit=limit)