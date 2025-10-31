import os, importlib, asyncio, pytest, httpx

pytestmark = pytest.mark.asyncio

def _env():
    os.environ["QUARANTINE_ENABLED"] = "false"
    os.environ["ZSCORE_ENABLED"] = "true"
    os.environ["ZSCORE_BUCKET_SEC"] = "1"
    os.environ["ZSCORE_WINDOW_MIN"] = "1"
    os.environ["ZSCORE_MIN_SAMPLES"] = "3"
    os.environ["ZSCORE_THRESHOLD"] = "2.0"
    os.environ["QUARANTINE_EXCLUDE_PATHS"] = "/_debug/alerts"

@pytest.mark.asyncio
async def test_zscore_alerts_when_spike():
    _env()
    import app.main as main
    importlib.reload(main)
    app = main.app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        # baseline: 3 kova ama farklı sayılar (std > 0 garantisi)
        for hits in (1, 2, 3):
            for _ in range(hits):
                await c.get("/health")
            await asyncio.sleep(1.05)
        # spike
        for _ in range(12):
            await c.get("/health")
        # emit'in event loop'ta işlenmesi için kısa polling
        kinds = set()
        for _ in range(10):
            await asyncio.sleep(0.05)
            r = await c.get("/_debug/alerts?limit=50")
            kinds = {a.get("kind") for a in r.json() if isinstance(a, dict)}
            if "zscore_anomaly" in kinds:
                break
        assert "zscore_anomaly" in kinds
