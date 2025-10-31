from dotenv import load_dotenv
load_dotenv()  # .env'yi import zincirinden önce yükle
import os


# app/main.py
from fastapi import FastAPI
from starlette.responses import JSONResponse
from app.security.middleware_quarantine import QuarantineMiddleware
from app.security.middleware_monitor import MonitorMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.api.routes_events import router as events_router, stats_router
from app.db.session import get_session, SessionLocal
from app.services.retention import run_retention

from app.api.routes_debug import router as debug_router
from app.api.routes_metrics import router as metrics_router
from app.metrics import get_metrics
from app.alerts import AlertManager


# --- Ana app

app = FastAPI(title="Sec-Mon")

# Latency middleware'ı en dış katmana ekleyelim
try:
    from app.observability.middleware_latency import LatencyMiddleware
    app.add_middleware(LatencyMiddleware)
except Exception:
    pass

# ---- Metrics: tek kez kur ve app.state'e sabitle ----
_metrics = get_metrics()
app.state.secmon_metrics = _metrics

# ---- ALERTS: tek instance (opsiyonel sink ile)
app.state.alerts = AlertManager(
    cooldown_seconds=int(os.getenv("ALERT_COOLDOWN_SECONDS", "60")),
    keep_recent=int(os.getenv("ALERT_KEEP_RECENT", "200")),
)
try:
    from app.alerts.sinks import StdoutSink  # type: ignore
    app.state.alerts.register(StdoutSink())
except Exception:
    # StdoutSink tanımlı değilse sorun değil; uygulama normal çalışsın
    pass
try:
    if os.getenv("ALERT_FILE_PATH"):
        from app.alerts.sinks import FileSink  # type: ignore
        app.state.alerts.register(FileSink(os.getenv("ALERT_FILE_PATH")))
except Exception:
    pass
try:
    if os.getenv("ALERT_WEBHOOK_URL"):
        from app.alerts.sinks import WebhookSink  # type: ignore
        app.state.alerts.register(WebhookSink(os.getenv("ALERT_WEBHOOK_URL")))
except Exception:
    pass

# 2) Debug config endpoint (istediğin gibi)
@app.get("/_debug/config")
def debug_config():
    import os
    keys = [
        "QUARANTINE_ENABLED",
        "QUARANTINE_BLOCK_STATUS",
        "QUARANTINE_REQUIRE_Z",
        "QUARANTINE_BAN_SECONDS",
        "RATE_WINDOW_SECONDS",
        "RATE_THRESHOLD",
        "QUARANTINE_DEBUG",
    ]
    return {"env": {k: os.environ.get(k) for k in keys}}

# 3) Basit health
@app.get("/health")
def health():
    return JSONResponse({"status": "ok"})

# 4) (Varsa) diğer router import/include'ların burada kalsın
# from app.api.routes_events import router as events_router
app.include_router(metrics_router)
try:
    from app.api.routes_debug_banlist import router as debug_banlist_router
    app.include_router(debug_banlist_router)
except Exception:
    pass
try:
    from app.api.routes_debug_whoami import router as debug_whoami_router
    app.include_router(debug_whoami_router)
except Exception:
    pass
try:
    from app.api.routes_debug_alerts import router as debug_alerts_router
    app.include_router(debug_alerts_router)
except Exception:
    pass
app.include_router(events_router)
app.include_router(stats_router)

app.include_router(debug_router)

@app.on_event("startup")
async def _startup():
    # APScheduler
    app.state.scheduler = AsyncIOScheduler()
    # Her gün 03:30'da retention
    app.state.scheduler.add_job(_retention_job, CronTrigger(hour=3, minute=30))
    app.state.scheduler.start()

async def _retention_job():
    # bağımsız bir session açıp retention çalıştır
    async with SessionLocal() as session:
        deleted = await run_retention(session)
        await session.commit()
        # print(f"[retention] deleted={deleted}")

@app.on_event("shutdown")
async def _shutdown():
    sch = getattr(app.state, "scheduler", None)
    if sch:
        sch.shutdown(wait=False)

# 5) MIDDLEWARE SIRASI (Monitor en son eklenecek -> ilk çalışır)
# Starlette: En son eklenen middleware ilk çalışır (outermost).
# Bu yüzden IP hash ve pencere sayacı için Monitor en son eklenir,
# bloklama ve metrik artışı Quarantine tarafında yapılır.
app.add_middleware(
    QuarantineMiddleware,
    metrics=_metrics,  # aynı Counter/Gauge referanslarını DI ile geçir
    # exclude_paths içinde yalnızca güvenli uçlar olsun; /health burada YOK!
    # Örn: /metrics ve /_debug/config muaf tutulsun:
    exclude_paths="/metrics,/_debug/config",
)
app.add_middleware(MonitorMiddleware)