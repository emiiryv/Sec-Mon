# app/db/session.py
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or "asyncpg" not in DATABASE_URL:
    raise RuntimeError("DATABASE_URL (asyncpg) env değişkeni gerekli, örn: postgresql+asyncpg://user:pass@localhost:5432/secmon")

is_test = os.getenv("APP_ENV") == "test" or os.getenv("PYTEST_CURRENT_TEST") is not None

engine_kwargs = dict(
    echo=False,
    pool_pre_ping=True,
)

if is_test:
    # Her test çağrısında yeni bağlantı, loop karışmasın
    engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, autocommit=False)

async def get_session():
    async with SessionLocal() as session:
        yield session