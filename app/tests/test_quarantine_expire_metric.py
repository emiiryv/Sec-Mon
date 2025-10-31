

import os, importlib, asyncio, pytest, httpx
from prometheus_client.parser import text_string_to_metric_families

pytestmark = pytest.mark.asyncio

def _set_env():
    os.environ["QUARANTINE_ENABLED"] = "true"
    os.environ["QUARANTINE_BLOCK_STATUS"] = "403"
    os.environ["QUARANTINE_REQUIRE_Z"] = "false"
    os.environ["QUARANTINE_BAN_SECONDS"] = "1"
    os.environ["RATE_WINDOW_SECONDS"] = "1"
    os.environ["RATE_THRESHOLD"] = "2"
    os.environ["QUARANTINE_EXCLUDE_PATHS"] = "/metrics"

def _get_metric(txt: str, name: str) -> float:
    for fam in text_string_to_metric_families(txt):
        if fam.name == name:
            return sum(float(s.value) for s in fam.samples)
    return 0.0

@pytest.mark.asyncio
async def test_quarantine_ipcount_expires_back_to_zero():
    _set_env()
    import app.main as main
    importlib.reload(main)
    app = main.app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        # ban tetikle
        for _ in range(4):
            await c.get("/health")
        # gauge >=1 olmalı
        m1 = await c.get("/metrics")
        g1 = _get_metric(m1.text, "quarantined_ip_count")
        assert g1 >= 1.0
        # expire’ı bekle
        await asyncio.sleep(1.2)
        # yeni bir istek prune’ı çalıştırır
        await c.get("/health")
        m2 = await c.get("/metrics")
        g2 = _get_metric(m2.text, "quarantined_ip_count")
        assert g2 <= 0.0