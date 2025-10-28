from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.settings import get_settings

class Base(DeclarativeBase):
    pass

_settings = get_settings()
engine = create_async_engine(_settings.DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

async def init_models():
    from app.persistence import models  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)