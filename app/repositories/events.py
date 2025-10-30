# app/repositories/events.py
from datetime import datetime
from typing import Sequence, Any, Optional

from sqlalchemy import select, func, desc, and_, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Event

async def insert_event(
    session: AsyncSession,
    *,
    ip_hash: str,
    ua: Optional[str],
    path: Optional[str],
    reason: Optional[str],
    score: Optional[float],
    severity: Optional[int],
    meta: Optional[dict],
) -> int:
    # ts=func.now() kritik: NOT NULL ts için DB tarafında timestamp atar
    stmt = (
        insert(Event.__table__)
        .values(
            ts=func.now(),
            ip_hash=ip_hash,
            ua=ua,
            path=path,
            reason=reason,
            score=score,
            severity=severity,
            meta=meta,
        )
        .returning(Event.__table__.c.id)
    )
    res = await session.execute(stmt)
    return res.scalar_one()

async def list_events(
    session: AsyncSession,
    *,
    start_ts: Optional[datetime],
    end_ts: Optional[datetime],
    reason: Optional[str],
    path: Optional[str],
    ip_hash: Optional[str],
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, Sequence[Event]]:
    conds = []
    if start_ts:
        conds.append(Event.ts >= start_ts)
    if end_ts:
        conds.append(Event.ts < end_ts)
    if reason:
        conds.append(Event.reason == reason)
    if path:
        conds.append(Event.path == path)
    if ip_hash:
        conds.append(Event.ip_hash == ip_hash)

    where = and_(*conds) if conds else None

    q_count = select(func.count()).select_from(Event if where is None else select(Event).where(where).subquery())
    total = (await session.execute(q_count)).scalar_one()

    q = select(Event).order_by(desc(Event.ts)).limit(limit).offset(offset)
    if where is not None:
        q = select(Event).where(where).order_by(desc(Event.ts)).limit(limit).offset(offset)

    rows = (await session.execute(q)).scalars().all()
    return total, rows

async def daily_counts(session: AsyncSession, days: int = 7):
    q = select(
        func.date_trunc("day", Event.ts).label("day"),
        func.count().label("cnt")
    ).group_by(func.date_trunc("day", Event.ts)).order_by(func.date_trunc("day", Event.ts))
    if days:
        q = q.where(Event.ts >= func.now() - func.make_interval(days=days))
    return (await session.execute(q)).all()

async def top_reason_counts(session: AsyncSession, limit: int = 10):
    q = select(Event.reason, func.count().label("cnt")).group_by(Event.reason).order_by(desc("cnt")).limit(limit)
    return (await session.execute(q)).all()

async def top_paths(session: AsyncSession, limit: int = 10):
    q = select(Event.path, func.count().label("cnt")).group_by(Event.path).order_by(desc("cnt")).limit(limit)
    return (await session.execute(q)).all()