# app/main.py
from fastapi import FastAPI, Response
from starlette.responses import JSONResponse
from app.security.middleware_monitor import MonitorMiddleware
from app.security.middleware_quarantine import QuarantineMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, REGISTRY

# --- Ana app
app = FastAPI(title="Sec-Mon")

# 1) Prometheus metrics endpoint (inline route; no redirect)
@app.get("/metrics", include_in_schema=False)
def metrics():
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

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
# app.include_router(events_router)

# 5) MIDDLEWARE SIRASI
# Not: Burada sırayı değiştirmiyoruz; mevcut "doğru" sıran neyse aynen koru.
app.add_middleware(MonitorMiddleware)
app.add_middleware(QuarantineMiddleware)