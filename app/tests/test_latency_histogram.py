

import os, importlib, pytest, httpx
from prometheus_client.parser import text_string_to_metric_families

pytestmark = pytest.mark.asyncio

@pytest.mark.asyncio
async def test_latency_histogram_counts():
    # Gürültü engelle: zscore/karantina kapalı
    os.environ["ZSCORE_ENABLED"] = "false"
    os.environ["QUARANTINE_ENABLED"] = "false"
    os.environ["QUARANTINE_EXCLUDE_PATHS"] = "/metrics"

    import app.main as main
    importlib.reload(main)
    app = main.app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        # Birkaç istek gönder
        N = 5
        for _ in range(N):
            await c.get("/health")

        # Metrikleri çek
        r = await c.get("/metrics")
        txt = r.text

        # Histogram'ın doğru numaralandığını doğrula:
        # Prometheus, histogramı tek "request_latency_seconds" ailesi altında
        # *_bucket, *_count ve *_sum örnekleriyle export eder.
        total = 0.0
        for fam in text_string_to_metric_families(txt):
            if fam.name == "request_latency_seconds":
                for s in fam.samples:
                    if getattr(s, "name", "") == "request_latency_seconds_count":
                        try:
                            total += float(s.value)
                        except Exception:
                            pass

        assert total >= N