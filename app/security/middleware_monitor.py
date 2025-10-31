import os
import time
import hashlib
import asyncio
from collections import defaultdict, deque
from typing import Deque, Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from starlette.responses import Response
# Alerts (optional, new path)
from app.alerts import AlertManager, make_payload  # noqa: F401

__all__ = ["MonitorMiddleware"]

# --- Yardımcılar -------------------------------------------------------------

def _now() -> float:
    return time.time()

def _client_ip(request: Request) -> str:
    # X-Forwarded-For ilk IP > yoksa request.client.host
    xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if xff:
        # "a, b, c" -> "a"
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"

def _ip_hash(ip: str) -> str:
    # Loglarındaki formatla uyumlu 16 hexdigit
    return hashlib.md5(ip.encode("utf-8")).hexdigest()[:16]

def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")

def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except Exception:
        return default

def _inc_metric_suspicious(ip_hash: str, reason: str) -> None:
    # İçe import: import-time hatalarını önler
    try:
        from app.metrics import SUSPICIOUS_REQUESTS
        # Tek label şeması: client
        SUSPICIOUS_REQUESTS.labels(client=ip_hash).inc()
    except Exception:
        pass

def _create_event(request: Request, ip_hash: str, reason: str, severity: int = 1) -> None:
    """
    DB event yazımı uygulamaya gömükse burada içe import yapıyoruz.
    İçe import başarısızsa sessiz geçiyoruz.
    """
    try:
        # Örnek bir event kaydedici fonksiyon adı. Projene uygun şekilde
        # routes_events içinde ya da repo katmanında neyse onu import et.
        from app.api.routes_events import create_event_programmatic  # type: ignore
        ua = request.headers.get("User-Agent", "-")
        path = request.url.path
        meta = {"client_ip_masked": True}
        create_event_programmatic(ip_hash=ip_hash, ua=ua, path=path, reason=reason, severity=severity, meta=meta)
    except Exception:
        # Opsiyonel: log'a yaz
        # print(f"[monitor] event yazılamadı: {reason}")
        pass

def _quarantine_ip(ip_hash: str, seconds: int) -> None:
    """Monitor sadece karantinayı işaretler; 403'ü QuarantineMiddleware verir."""
    try:
        from app.security.middleware_quarantine import add_quarantine
        add_quarantine(ip_hash)  # süre, middleware_quarantine içindeki settings’e göre uygulanır
    except Exception:
        pass


# --- Rate limitleme state'i (in-memory) -------------------------------------
# ip_hash -> deque[timestamps]
_RATE_BUCKETS: Dict[str, Deque[float]] = defaultdict(deque)


class MonitorMiddleware(BaseHTTPMiddleware):
    """
    - IP/UA bilgisini okuyup request.state içine yazar.
    - 'curl/', 'sqlmap', 'nikto' gibi ajanları 'suspicious_ua' olarak işaretler.
    - RATE_WINDOW_SECONDS içinde RATE_THRESHOLD'i aşan isteklerde 'rate_abuse' üretir
      ve QUARANTINE_ENABLED ise ip'yi QUARANTINE_BAN_SECONDS süreyle banlar.
    - Metrikleri ve (varsa) event tablosunu günceller.
    """

    def __init__(self, app):
        super().__init__(app)
        self.rate_window = float(_env_int("RATE_WINDOW_SECONDS", 1))
        self.rate_threshold = _env_int("RATE_THRESHOLD", 20)
        self.quarantine_enabled = _env_bool("QUARANTINE_ENABLED", False)
        self.quarantine_seconds = _env_int("QUARANTINE_BAN_SECONDS", 600)

    async def dispatch(self, request: Request, call_next):
        ip = _client_ip(request)
        ip_h = _ip_hash(ip)
        ua = request.headers.get("User-Agent", "")

        # state'e yazalım ki QuarantineMiddleware tekrar hesaplamak zorunda kalmasın
        request.state.client_ip = ip
        request.state.ip_hash = ip_h
        request.state.monitor = {}

        # 1) UA kontrolü
        suspicious = False
        ua_lc = ua.lower()
        if ua_lc.startswith("curl/") or "sqlmap" in ua_lc or "nikto" in ua_lc:
            suspicious = True
            _inc_metric_suspicious(ip_h, "suspicious_ua")
            _create_event(request, ip_h, reason="suspicious_ua", severity=1)

        # 2) Rate limitleme (sliding window)
        now = _now()
        bucket = _RATE_BUCKETS[ip_h]
        bucket.append(now)
        # Pencere dışındakileri temizle
        cutoff = now - self.rate_window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) > self.rate_threshold:
            # Rate abuse
            _inc_metric_suspicious(ip_h, "rate_abuse")
            _create_event(request, ip_h, reason="rate_abuse", severity=2)

            if self.quarantine_enabled:
                _quarantine_ip(ip_h, self.quarantine_seconds)
                # Alert (fire-and-forget): rate abuse eşiği aşıldı
                try:
                    alerts = getattr(request.app.state, "alerts", None)
                    if alerts is not None:
                        meta = {"count": len(bucket), "win": self.rate_window}
                        asyncio.create_task(
                            alerts.emit(
                                make_payload(
                                    "rate_abuse",
                                    ip_h,
                                    request.url.path,
                                    "threshold_exceeded",
                                    meta,
                                )
                            )
                        )
                except Exception:
                    pass

        # İsteği devam ettir
        response: Response = await call_next(request)
        return response