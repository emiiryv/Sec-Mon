from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.persistence.models import Event

async def insert_event(
    session: AsyncSession,
    *,
    ts: datetime,
    ip_hash: str,
    ua: str | None,
    path: str,
    reason: str,
    score: float | None = None,
    severity: int = 0,
    meta: dict | None = None,
):
    ev = Event(ts=ts, ip_hash=ip_hash, ua=ua, path=path, reason=reason, score=score, severity=severity, meta=meta)
    session.add(ev)
    await session.commit()
    return ev.id

async def query_events(
    session: AsyncSession,
    *,
    ip_hash: str | None = None,
    reason: str | None = None,
    since: datetime | None = None,
    limit: int = 200,
):
    stmt = select(Event).order_by(Event.ts.desc()).limit(limit)
    if ip_hash:
        stmt = stmt.where(Event.ip_hash == ip_hash)
    if reason:
        stmt = stmt.where(Event.reason == reason)
    if since:
        stmt = stmt.where(Event.ts >= since)
    res = await session.execute(stmt)
    rows = res.scalars().all()
    return [dict(
        id=r.id, ts=r.ts.isoformat(), ip_hash=r.ip_hash, ua=r.ua, path=r.path,
        reason=r.reason, score=r.score, severity=r.severity, meta=r.meta
    ) for r in rows]

async def daily_summary(session: AsyncSession):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=1)
    stmt = select(Event.reason, func.count(Event.id)).where(Event.ts >= since).group_by(Event.reason)
    res = await session.execute(stmt)
    return {reason: count for reason, count in res.all()}

async def retention_purge(session: AsyncSession, days: int):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = delete(Event).where(Event.ts < cutoff)
    await session.execute(stmt)
    await session.commit()