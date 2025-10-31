import json, asyncio
from pathlib import Path
from dataclasses import asdict

# Not: httpx projede zaten testlerde kullanılıyor; buradan da yararlanıyoruz.
try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None  # WebhookSink kullanan yoksa sorun olmaz.

# yeni taban tipleri: app.alerts.base
from app.alerts.base import AlertPayload, AlertSink
from typing import Optional, Dict, Any
import os
# opsiyonel: metrik erişimi (ileride kullanılabilir)
from app.metrics import METRICS_REGISTRY  # noqa: F401

class ConsoleSink(AlertSink):
    async def send(self, payload: AlertPayload) -> None:
        print("[ALERT]", json.dumps(asdict(payload), ensure_ascii=False))

class FileSink(AlertSink):
    """
    Basit dosya sink'i. Satır başı JSON yazar. Bloklamamak için yazımı thread'e offload eder.
    """
    def __init__(self, path: str):
        self.path = path
        # klasör yoksa oluştur
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        except Exception:
            pass

    async def send(self, payload: AlertPayload) -> None:
        line = json.dumps({
            "ts": payload.ts,
            "kind": payload.kind,
            "ip_hash": payload.ip_hash,
            "path": payload.path,
            "reason": payload.reason,
            "meta": payload.meta,
            "host": payload.host,
            "env": payload.env,
        }, ensure_ascii=False)

        async def _write():
            # a+ ile sonuna ekle
            with open(self.path, "a+", encoding="utf-8") as f:
                f.write(line + "\n")

        # Dosya IO'yu thread'e at
        await asyncio.to_thread(lambda: asyncio.run(_write()))

class WebhookSink(AlertSink):
    """
    Basit webhook sink'i. JSON POST eder.
    """
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None, timeout_sec: float = 3.0):
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self.timeout = timeout_sec

    async def send(self, payload: AlertPayload) -> None:
        if httpx is None:
            return  # httpx yoksa sessiz geç
        body: Dict[str, Any] = {
            "ts": payload.ts,
            "kind": payload.kind,
            "ip_hash": payload.ip_hash,
            "path": payload.path,
            "reason": payload.reason,
            "meta": payload.meta,
            "host": payload.host,
            "env": payload.env,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                await client.post(self.url, headers=self.headers, json=body)
        except Exception:
            # Sprint 2'de basit bırakıyoruz (retry/backoff sonraki sprintte)
            pass

class StdoutSink:
    async def send(self, payload: AlertPayload) -> None:
        # Basit log; JSON yerine alanları tek tek yazdırır
        print(
            "[ALERT]",
            payload.kind,
            payload.ip_hash,
            payload.path,
            payload.reason,
            payload.meta,
        )