# app/security/middleware_quarantine.py
import os
import time
import hashlib
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse
from prometheus_client import Counter, Gauge

# ---- Prometheus metrics (tam da grep ettiğin isimlerle) ----
SUSPICIOUS_REQUESTS = Counter(
    "suspicious_requests_total",
    "Requests observed by quarantine middleware",
    ["client"],
)
QUARANTINED_BLOCKS = Counter(
    "quarantined_blocks_total",
    "Requests blocked by quarantine middleware",
    ["client"],
)
QUARANTINED_IP_COUNT = Gauge(
    "quarantined_ip_count",
    "Currently quarantined unique clients",
)

def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")

def _now() -> float:
    return time.time()

class QuarantineMiddleware(BaseHTTPMiddleware):
    """
    Basit rate-limit & karantina:
      - RATE_WINDOW_SECONDS içinde RATE_THRESHOLD'u aşan client 'ban' süresi kadar bloklanır.
      - QUARANTINE_EXCLUDE_PATHS ile belirli path'ler tamamen bypass edilir (örn. /metrics).
    """
    def __init__(self, app):
        super().__init__(app)
        self.enabled = _env_flag("QUARANTINE_ENABLED", "false")
        self.block_status = int(os.getenv("QUARANTINE_BLOCK_STATUS", "403"))
        self.require_z  = _env_flag("QUARANTINE_REQUIRE_Z", "false")
        self.ban_seconds = int(os.getenv("QUARANTINE_BAN_SECONDS", "600"))
        self.win_seconds = int(os.getenv("RATE_WINDOW_SECONDS", "1"))
        self.threshold   = int(os.getenv("RATE_THRESHOLD", "20"))
        self.debug = _env_flag("QUARANTINE_DEBUG", "0")

        # Örn: "/metrics,/_debug/config"
        raw_ex = os.getenv("QUARANTINE_EXCLUDE_PATHS", "/metrics")
        self.excluded_paths = [p.strip() for p in raw_ex.split(",") if p.strip()]

        # In-memory state: key -> {"w": window_start_ts, "c": count, "ban": banned_until_ts}
        self.state: dict[str, dict] = {}

        # Metriklerin görünmesi için en az bir child oluştur (0 arttırma yeterli)
        SUSPICIOUS_REQUESTS.labels(client="init").inc(0)
        QUARANTINED_BLOCKS.labels(client="init").inc(0)
        QUARANTINED_IP_COUNT.set(0)

    def _is_excluded(self, path: str) -> bool:
        for p in self.excluded_paths:
            if path == p or path.startswith(p + "/"):
                return True
        return False

    def _client_key(self, client_ip: str) -> str:
        # Senin log’larda gördüğün 16 hanelik md5 benzeri ID’yi üretelim
        return hashlib.md5(client_ip.encode("utf-8")).hexdigest()[:16]

    def _client_ip(self, request) -> str:
        xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if xff:
            # 1. IP'yi al
            return xff.split(",")[0].strip()
        # fallback
        return (request.client.host if request.client and request.client.host else "unknown")

    def _update_gauge(self, now_ts: float) -> None:
        # Şu an banlı olan benzersiz client sayısı
        active = sum(1 for rec in self.state.values() if rec.get("ban", 0) > now_ts)
        QUARANTINED_IP_COUNT.set(active)

    async def dispatch(self, request, call_next):
        path = request.url.path

        # 1) Exclude path'ler: karantinayı tamamen bypass et
        if self._is_excluded(path):
            return await call_next(request)

        # 2) Global enable kapalıysa dokunma
        if not self.enabled:
            return await call_next(request)

        # 3) (Opsiyonel) Z-header şartı
        if self.require_z and ("Z" not in request.headers and "z" not in request.headers):
            # Z gereksinimi varsa ve yoksa direkt blocklamıyoruz; normal işleyişe devam.
            # (İstersen burada da block davranışı tanımlayabilirsin)
            pass

        now_ts = _now()
        client_ip = self._client_ip(request)
        key = self._client_key(client_ip)

        rec = self.state.get(key, {"w": now_ts, "c": 0, "ban": 0.0})

        # 4) Ban kontrol
        if rec["ban"] > now_ts:
            if self.debug:
                print(f"[quarantine] BLOCK {key} -> {self.block_status}")
            QUARANTINED_BLOCKS.labels(client=key).inc()
            self._update_gauge(now_ts)
            return PlainTextResponse(f"Quarantined ({key})", status_code=self.block_status)

        # 5) Pencere ve sayaç
        if now_ts - rec["w"] <= self.win_seconds:
            rec["c"] += 1
        else:
            rec["w"] = now_ts
            rec["c"] = 1

        # Metrik
        SUSPICIOUS_REQUESTS.labels(client=key).inc()

        # 6) Eşik aşıldı mı?
        if rec["c"] > self.threshold:
            rec["ban"] = now_ts + self.ban_seconds
            if self.debug:
                print(f"[quarantine] BAN set for {key} for {self.ban_seconds}s")
                print(f"[quarantine] BLOCK {key} -> {self.block_status}")
            self.state[key] = rec
            QUARANTINED_BLOCKS.labels(client=key).inc()
            self._update_gauge(now_ts)
            return PlainTextResponse(f"Quarantined ({key})", status_code=self.block_status)

        self.state[key] = rec
        # gauge'i nadiren de olsa güncellemek faydalı (maliyet çok düşük)
        self._update_gauge(now_ts)

        return await call_next(request)