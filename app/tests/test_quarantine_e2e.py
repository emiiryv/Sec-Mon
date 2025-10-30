import os
import asyncio
import importlib
import pytest
import httpx
import re
from prometheus_client.parser import text_string_to_metric_families

pytestmark = pytest.mark.asyncio

def _sum_metric(txt: str, name: str) -> float:
    """
    Prometheus text formatında hem labelsız hem label'lı örnekleri toplar.
    Örn:
      name 12
      name{foo="bar"} 7
    """
    patt = rf'^{re.escape(name)}(?:\{{[^}}]*\}})?\s+([0-9.eE+-]+)$'
    total = 0.0
    for m in re.finditer(patt, txt, re.MULTILINE):
        try:
            total += float(m.group(1))
        except Exception:
            pass
    return total

def _set_env():
    os.environ["QUARANTINE_ENABLED"] = "true"
    os.environ["QUARANTINE_BLOCK_STATUS"] = "403"
    os.environ["QUARANTINE_REQUIRE_Z"] = "false"
    os.environ["QUARANTINE_BAN_SECONDS"] = "60"
    os.environ["RATE_WINDOW_SECONDS"] = "1"
    os.environ["RATE_THRESHOLD"] = "5"
    os.environ["QUARANTINE_DEBUG"] = "1"
    os.environ["QUARANTINE_EXCLUDE_PATHS"] = "/metrics,/_debug/config"

@pytest.mark.asyncio
async def test_quarantine_blocks_and_metrics_and_event(monkeypatch):
    _set_env()
    # App’i env set edildikten sonra yeniden yükle
    import app.main as main
    importlib.reload(main)
    app = main.app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Eşik üstü istek at
        for _ in range(8):
            await client.get("/health")

        # Artık 403 beklenir
        r = await client.get("/health")
        assert r.status_code == 403

        # Metriklere bak (event loop'un increment'i yazmasına minicik fırsat ver)
        await asyncio.sleep(0.02)
        m = await client.get("/metrics")
        assert m.status_code == 200
        txt = m.text

        # Sayaçlardan en az biri artmış olmalı
        assert "suspicious_requests_total" in txt
        assert "quarantined_blocks_total" in txt
        assert "quarantined_ip_count" in txt

        # Basit bir doğrulama: blocked counter value > 0 (küçük poll ile)
        blocked_total = 0.0
        for _ in range(5):
            m = await client.get("/metrics")
            assert m.status_code == 200
            txt = m.text
            blocked_total = _sum_metric(txt, "quarantined_blocks_total")
            if blocked_total > 0:
                break
            await asyncio.sleep(0.05)

        assert blocked_total > 0

        # Opsiyonel: DB event’ini doğrulamak için stats endpoint’in varsa:
        # stats = await client.get("/stats/events?limit=1")
        # assert stats.status_code == 200