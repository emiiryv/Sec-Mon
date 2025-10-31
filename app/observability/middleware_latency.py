

import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.metrics import REQUEST_LATENCY

EXCLUDE_PREFIXES = ("/metrics",)

class LatencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path or "/"
        if any(path.startswith(p) for p in EXCLUDE_PREFIXES):
            # /metrics gibi uçları ölçmeyelim
            return await call_next(request)

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        finally:
            duration = time.perf_counter() - start
            # route şablonu varsa onu kullan, yoksa gerçek path
            route_tpl = path
            try:
                r = request.scope.get("route")
                if r and getattr(r, "path", None):
                    route_tpl = r.path
            except Exception:
                pass
            status = "0"
            try:
                status = str(getattr(response, "status_code", 0))
            except Exception:
                pass
            try:
                REQUEST_LATENCY.labels(route=route_tpl, method=request.method, status=status).observe(duration)
            except Exception:
                pass
        return response