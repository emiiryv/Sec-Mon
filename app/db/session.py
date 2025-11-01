# app/db/session.py
import os
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or "asyncpg" not in DATABASE_URL:
    raise RuntimeError("DATABASE_URL (asyncpg) env değişkeni gerekli, örn: postgresql+asyncpg://user:pass@localhost:5432/secmon")

# TEST tespiti: pytest veya ENV=test/ci ise havuzu kapat (loop çakışmasını önler)
_IS_TEST = bool(os.getenv("PYTEST_CURRENT_TEST")) or os.getenv("ENV") in {"test", "ci"}

ENGINE_OPTS = {"echo": False, "future": True, "pool_pre_ping": True}

if _IS_TEST:
    # Her çağrıda yeni bağlantı: farklı event loop'larda güvenli
    ENGINE_OPTS["poolclass"] = NullPool

engine = create_async_engine(DATABASE_URL, **ENGINE_OPTS)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session