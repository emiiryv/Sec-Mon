# app/security/middleware_quarantine.py
import os
import time
import hashlib
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse
from app.alerts import make_payload
from app.security.ip_utils import get_client_info, is_allowlisted
from time import time
import asyncio
from typing import Optional, Dict, Any, Dict as _Dict
from app.db.session import SessionLocal
from app.repositories.events import insert_event


# Process-local shadow counter (pytest/sade parserlar için deterministik toplama)
BLOCKS_SHADOW_TOTAL: int = 0

def _inc_shadow_blocks(n: int = 1) -> None:
    """Process-local toplamı güvenli biçimde artır."""
    global BLOCKS_SHADOW_TOTAL
    BLOCKS_SHADOW_TOTAL += n

# Aktif banları (expires ts) process-local olarak da izleyelim
_quarantine: Dict[str, float] = {}


# --- Metriklere erişim için çoklu-fallback ---
try:
    # Eğer singleton'lı erişim fonksiyonumuz varsa onu kullanacağız
    from app.metrics import get_metrics as _get_metrics  # type: ignore
except Exception:
    _get_metrics = None  # type: ignore

def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")

class QuarantineMiddleware(BaseHTTPMiddleware):
    """
    Basit rate-limit & karantina:
      - RATE_WINDOW_SECONDS içinde RATE_THRESHOLD'u aşan client 'ban' süresi kadar bloklanır.
      - QUARANTINE_EXCLUDE_PATHS ile belirli path'ler tamamen bypass edilir (örn. /metrics).
    """
    def __init__(self, app, *, metrics: Optional[Dict[str, Any]] = None, **kwargs):
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

        # ---- Metrics wiring (Dependency Injection) ----
        # 3 kademeli sağlam kablolama:
        # 1) app.state'ten, 2) get_metrics() ile singleton'dan, 3) doğrudan sayaç import
        wired: Optional[_Dict[str, Any]] = None

        # 1) app.state üzerinden verilmişse
        if metrics is None:
            if hasattr(app.state, "secmon_metrics"):
                wired = getattr(app.state, "secmon_metrics")
            elif hasattr(app.state, "metrics"):
                wired = getattr(app.state, "metrics")

        # 2) erişim fonksiyonundan çek
        if wired is None and metrics is None and _get_metrics is not None:
            try:
                wired = _get_metrics()
            except Exception:
                wired = None

        # 3) son çare: direkt tekil sayaç nesnelerini import et
        if wired is None and metrics is None:
            try:
                from app.metrics import (  # type: ignore
                    METRICS_REGISTRY as _REG,
                    SUSPICIOUS_REQUESTS as _SUS,
                    QUARANTINED_BLOCKS as _BLK,
                    QUARANTINED_IP_COUNT as _IPC,
                )
                wired = {"registry": _REG, "suspicious": _SUS, "blocked": _BLK, "ipcount": _IPC}
            except Exception:
                wired = None

        # Dışarıdan parametre geldiyse o öncelikli
        if metrics is not None:
            wired = metrics

        self._registry = wired["registry"] if wired else None
        self._suspicious = wired["suspicious"] if wired else None
        self._blocked = wired["blocked"] if wired else None
        self._ipcount = wired["ipcount"] if wired else None

        # Debug görünürlüğü
        if self.debug:
            print(
                f"[quarantine] metrics wired: "
                f"blocked={'ok' if self._blocked else 'none'}, "
                f"suspicious={'ok' if self._suspicious else 'none'}, "
                f"ipcount={'ok' if self._ipcount else 'none'}"
            )

    def _now(self) -> float:
        import time
        return time.time()

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

    def _update_gauge(self, now_ts: float, touch_key: str | None = None):
        active = 0
        for k, v in self.state.items():
            ban_until = v.get("ban", 0)
            if ban_until > now_ts:
                active += 1
            elif ban_until > 0 and ban_until <= now_ts:
                # süre dolmuşsa temizle
                v["ban"] = 0
        if self._ipcount is not None:
            try:
                self._ipcount.set(active)
            except Exception:
                if self.debug:
                    print("[quarantine] gauge set failed (ignored)")

    async def dispatch(self, request, call_next):
        path = request.url.path

        now_ts = time()
        # expire olanları temizle ve gauge’i düzelt
        self._prune(now_ts)

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

        # now_ts = self._now()  # removed as per instructions

        # client_ip = self._client_ip(request)
        # key = self._client_key(client_ip)
        # replaced with:
        # trusted proxy & hash
        ip, key = get_client_info(request)
        # allowlist ise tamamen bypass
        if is_allowlisted(ip, key):
            return await call_next(request)

        rec = self.state.get(key, {"w": now_ts, "c": 0, "ban": 0.0})

        # Monitor’ün yazdığı harici ban’ı state’e merge et (varsa)
        try:
            ext_ban = float(_quarantine.get(key, 0.0))
        except Exception:
            ext_ban = 0.0
        if ext_ban > now_ts and ext_ban > float(rec.get("ban", 0.0)):
            rec["ban"] = ext_ban
            self.state[key] = rec

        # Her isteği gözlemle (counter garanti)
        if self._suspicious is not None:
            try:
                self._suspicious.labels(client=key).inc()
            except Exception:
                if self.debug:
                    print("[quarantine] suspicious inc failed (ignored)")

        # 4) Ban kontrol
        if float(rec.get("ban", 0.0)) > now_ts:
            if self.debug:
                print(f"[quarantine] BLOCK {key} -> {self.block_status}")
            # deterministik: blok anında sayaç artır
            if self._blocked is not None:
                try:
                    self._blocked.labels(client=key).inc()
                except Exception:
                    if self.debug:
                        print("[quarantine] blocked inc failed (ignored)")
            # shadow counter'ı artır
            try:
                _inc_shadow_blocks()
            except Exception:
                pass
            # aktif ban map’ini ve gauge’u güncelle
            try:
                _quarantine[key] = rec["ban"]
            except Exception:
                pass
            self._recalc_ipcount(now_ts)

            # DB event write (blocked request while already banned)
            try:
                async with SessionLocal() as s:
                    await insert_event(
                        s,
                        ip_hash=key,
                        ua=request.headers.get("user-agent"),
                        path=str(request.url.path),
                        reason="quarantine_block",
                        score=None,
                        severity=2,
                        meta={"status": self.block_status, "phase": "already_banned"},
                    )
                    await s.commit()
            except Exception as e:
                if self.debug:
                    print(f"[quarantine] event write failed: {e}")

            # Alert (fire-and-forget) for active ban block
            try:
                alerts = getattr(request.app.state, "alerts", None)
                if alerts is not None:
                    asyncio.create_task(alerts.emit(
                        make_payload("quarantine_block", key, request.url.path, "active_ban")
                    ))
            except Exception:
                pass

            resp = PlainTextResponse("Blocked by quarantine", status_code=self.block_status)
            resp.headers["X-Quarantine"] = "1"
            return resp

        # 5) Pencere ve sayaç
        if now_ts - rec["w"] <= self.win_seconds:
            rec["c"] += 1
        else:
            rec["w"] = now_ts
            rec["c"] = 1

        # 6) Eşik aşıldı mı?
        if rec["c"] > self.threshold:
            rec["ban"] = now_ts + self.ban_seconds
            if self.debug:
                print(f"[quarantine] BAN set for {key} for {self.ban_seconds}s")
                print(f"[quarantine] BLOCK {key} -> {self.block_status}")
            self.state[key] = rec
            # deterministik: blok anında sayaç artır
            if self._blocked is not None:
                try:
                    self._blocked.labels(client=key).inc()
                except Exception:
                    if self.debug:
                        print("[quarantine] blocked inc failed (ignored)")
            # shadow counter'ı artır
            try:
                _inc_shadow_blocks()
            except Exception:
                pass
            # aktif ban map’ini ve gauge’u güncelle
            try:
                _quarantine[key] = rec["ban"]
            except Exception:
                pass
            self._recalc_ipcount(now_ts)

            # DB event write (ban just set)
            try:
                async with SessionLocal() as s:
                    await insert_event(
                        s,
                        ip_hash=key,
                        ua=request.headers.get("user-agent"),
                        path=str(request.url.path),
                        reason="quarantine_block",
                        score=None,
                        severity=2,
                        meta={
                            "status": self.block_status,
                            "phase": "ban_set",
                            "count": rec["c"],
                            "threshold": self.threshold,
                            "window_seconds": self.win_seconds,
                        },
                    )
                    await s.commit()
            except Exception as e:
                if self.debug:
                    print(f"[quarantine] event write failed: {e}")

            # Alert (fire-and-forget) when ban is set due to threshold
            try:
                alerts = getattr(request.app.state, "alerts", None)
                if alerts is not None:
                    meta = {"count": rec["c"], "threshold": self.threshold}
                    asyncio.create_task(alerts.emit(
                        make_payload("quarantine_block", key, request.url.path, "ban_set", meta)
                    ))
            except Exception:
                pass

            resp = PlainTextResponse("Blocked by quarantine", status_code=self.block_status)
            resp.headers["X-Quarantine"] = "1"
            return resp

        self.state[key] = rec
        # gauge'i nadiren de olsa güncellemek faydalı (maliyet çok düşük)
        self._update_gauge(now_ts)

        return await call_next(request)

    def _prune(self, now_ts: float) -> None:
        try:
            alive = 0
            dead = []
            for k, r in list(self.state.items()):
                if r.get("ban", 0.0) > now_ts:
                    alive += 1
                else:
                    dead.append(k)
            for k in dead:
                self.state.pop(k, None)
            if self._ipcount is not None:
                self._ipcount.set(float(alive))
        except Exception:
            pass

    def _recalc_ipcount(self, now_ts: float) -> None:
        """Gauge’u self.state’ten canlı ban sayısına göre deterministik hesapla."""
        try:
            alive = sum(1 for r in self.state.values() if r.get("ban", 0.0) > now_ts)
            if self._ipcount is not None:
                self._ipcount.set(float(alive))
        except Exception:
            pass