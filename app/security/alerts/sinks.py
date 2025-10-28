import json, asyncio
from pathlib import Path
import httpx

class AlertSink:
    async def send(self, payload: dict) -> None:  # interface
        raise NotImplementedError

class ConsoleSink(AlertSink):
    async def send(self, payload: dict) -> None:
        print("[ALERT]", json.dumps(payload, ensure_ascii=False))

class FileSink(AlertSink):
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    async def send(self, payload: dict) -> None:
        line = json.dumps(payload, ensure_ascii=False)
        self.path.write_text(self.path.read_text(encoding="utf-8") + line + "\n", encoding="utf-8") if self.path.exists() \
            else self.path.write_text(line + "\n", encoding="utf-8")

class WebhookSink(AlertSink):
    def __init__(self, url: str, retry_max: int = 3, backoff_ms: int = 250):
        self.url = url
        self.retry_max = retry_max
        self.backoff_ms = backoff_ms

    async def send(self, payload: dict) -> None:
        async with httpx.AsyncClient(timeout=5.0) as client:
            for i in range(self.retry_max):
                try:
                    await client.post(self.url, json=payload)
                    return
                except Exception:
                    await asyncio.sleep(self.backoff_ms / 1000.0)