import os
import pytest
from sqlalchemy import text
from app.db.session import SessionLocal
from app.repositories.events import insert_event

pytestmark = pytest.mark.asyncio

@pytest.mark.asyncio
async def test_insert_event_increases_count():
    # Test DB olarak .env’deki DATABASE_URL kullanılır.
    async with SessionLocal() as s:
        before = (await s.execute(text("select count(*) from events"))).scalar_one()
        await insert_event(
            s,
            ip_hash="unittest_hash",
            ua="pytest",
            path="/unittest",
            reason="unit_insert",
            score=0.0,
            severity=1,
            meta={"ut": True},
        )
        await s.commit()
        after = (await s.execute(text("select count(*) from events"))).scalar_one()
        assert after == before + 1