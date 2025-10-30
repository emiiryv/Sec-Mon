# app/services/retention.py
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "30"))

async def run_retention(session: AsyncSession) -> int:
    """
    Eski eventleri temizler, silinen satır sayısını döndürür.
    """
    q = text("DELETE FROM events WHERE ts < (now() - make_interval(days := :days))")
    res = await session.execute(q, {"days": RETENTION_DAYS})
    # res.rowcount bazı sürümlerde None olabilir; güvenli döndür
    return getattr(res, "rowcount", 0) or 0