from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.persistence.db import get_session
from app.persistence.repo import daily_summary, retention_purge
from app.core.settings import get_settings

router = APIRouter(prefix="/stats", tags=["stats"])
_settings = get_settings()

@router.get("/daily_summary")
async def get_daily_summary(session: AsyncSession = Depends(get_session)):
    return await daily_summary(session)

@router.post("/purge")
async def purge_retention(days: int = Query(default=None, ge=1, le=365), session: AsyncSession = Depends(get_session)):
    d = days if days is not None else _settings.RETENTION_DAYS
    await retention_purge(session, d)
    return {"ok": True, "purged_older_than_days": d}