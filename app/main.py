from dotenv import load_dotenv
load_dotenv()  # .env'yi import zincirinden önce yükle


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


# --- Ana app
app = FastAPI(title="Sec-Mon")

# ---- Metrics: tek kez kur ve app.state'e sabitle ----
_metrics = get_metrics()
app.state.secmon_metrics = _metrics

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