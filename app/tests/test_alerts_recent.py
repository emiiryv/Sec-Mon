

import os
import asyncio
import importlib
import pytest
import httpx

pytestmark = pytest.mark.asyncio

def _set_env():
    # Alert buffer açık
    os.environ["ALERT_KEEP_RECENT"] = "50"
    os.environ["ALERT_COOLDOWN_SECONDS"] = "1"
    # Quarantine/Rate
    os.environ["QUARANTINE_ENABLED"] = "true"
    os.environ["QUARANTINE_BLOCK_STATUS"] = "403"
    os.environ["QUARANTINE_REQUIRE_Z"] = "false"
    os.environ["QUARANTINE_BAN_SECONDS"] = "60"
    os.environ["RATE_WINDOW_SECONDS"] = "1"
    os.environ["RATE_THRESHOLD"] = "3"
    os.environ["QUARANTINE_DEBUG"] = "0"
    # Debug alert listesi karantinadan muaf olsun
    os.environ["QUARANTINE_EXCLUDE_PATHS"] = "/metrics,/_debug/config,/_debug/alerts"

@pytest.mark.asyncio
async def test_alerts_recent_list_populates(monkeypatch):
    _set_env()
    import app.main as main
    importlib.reload(main)
    app = main.app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Eşiği aş (rate abuse + quarantine block)
        for _ in range(5):
            await client.get("/health")

        # Event loop'a alert emit için kısa fırsat
        await asyncio.sleep(0.05)

        # Son uyarıları çek
        resp = await client.get("/_debug/alerts?limit=20")
        assert resp.status_code == 200
        data = resp.json()
        # En az bir alert olmalı
        assert isinstance(data, list)
        assert len(data) >= 1
        # Tür kontrolü (rate_abuse veya quarantine_block bekleriz)
        kinds = {item.get("kind") for item in data if isinstance(item, dict)}
        assert ("rate_abuse" in kinds) or ("quarantine_block" in kinds)