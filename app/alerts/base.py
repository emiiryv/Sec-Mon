from __future__ import annotations
from dataclasses import dataclass, asdict
from collections import deque
from typing import Dict, Any, List, Protocol, Optional, Tuple
import time, asyncio, json, socket, os

@dataclass
class AlertPayload:
    ts: float
    kind: str
    ip_hash: str
    path: str
    reason: str
    meta: Dict[str, Any] | None = None
    host: str = socket.gethostname()
    env: str = os.getenv("APP_ENV", "dev")

class AlertSink(Protocol):
    async def send(self, payload: AlertPayload) -> None: ...

class AlertManager:
    """
    Basit in-memory dedup/cooldown:
      key = (kind, ip_hash, path, reason)
      If now - last_sent < cooldown => suppress
    """
    def __init__(self, cooldown_seconds: int = 60, keep_recent: int = 0):
        self.cooldown = max(0, int(cooldown_seconds))
        self.sinks: List[AlertSink] = []
        self._last: Dict[Tuple[str,str,str,str], float] = {}
        self._recent = deque(maxlen=int(keep_recent)) if keep_recent > 0 else None
        # metrikler opsiyonel
        try:
            from app.metrics import METRICS_REGISTRY
            from prometheus_client import Counter, Gauge
            self.m_emitted = Counter("alerts_emitted_total","Emitted alerts",["sink"],registry=METRICS_REGISTRY)
            self.m_supp = Counter("alerts_suppressed_total","Suppressed by cooldown",registry=METRICS_REGISTRY)
            self.m_cache = Gauge("alert_cooldown_cache_size","Cooldown cache size",registry=METRICS_REGISTRY)
        except Exception:
            self.m_emitted = None; self.m_supp = None; self.m_cache = None

    def register(self, sink: AlertSink) -> None:
        self.sinks.append(sink)

    async def emit(self, payload: AlertPayload) -> None:
        key = (payload.kind, payload.ip_hash, payload.path, payload.reason)
        now = time.time()
        last = self._last.get(key, 0.0)
        if self.cooldown and (now - last) < self.cooldown:
            if self.m_supp: self.m_supp.inc()
            return
        self._last[key] = now
        if self.m_cache: self.m_cache.set(len(self._last))
        # sinks'e paralel yolla
        await asyncio.gather(*(self._send_one(s, payload) for s in self.sinks), return_exceptions=True)
        # dev/DEBUG için son olayları tut
        if self._recent is not None:
            try:
                self._recent.append(asdict(payload))
            except Exception:
                pass

    async def _send_one(self, sink: AlertSink, payload: AlertPayload) -> None:
        try:
            await sink.send(payload)
            if self.m_emitted: self.m_emitted.labels(sink=sink.__class__.__name__).inc()
        except Exception:
            # S2-B: burada retry/backoff eklenecek
            pass

    def recent(self, limit: int | None = None) -> List[Dict[str, Any]]:
        if self._recent is None:
            return []
        if not limit or limit <= 0:
            return list(self._recent)
        return list(self._recent)[-int(limit):]

def make_payload(kind: str, ip_hash: str, path: str, reason: str, meta: Optional[Dict[str,Any]]=None) -> AlertPayload:
    return AlertPayload(ts=time.time(), kind=kind, ip_hash=ip_hash, path=path, reason=reason, meta=meta or {})