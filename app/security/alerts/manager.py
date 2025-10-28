import time
from collections import defaultdict
from typing import List
from app.core.settings import get_settings
from app.security.alerts.sinks import AlertSink, ConsoleSink, FileSink, WebhookSink

_settings = get_settings()

_last_global_send = 0.0
_last_key_send = defaultdict(float)  # key -> ts

def _build_sinks() -> List[AlertSink]:
    sinks: List[AlertSink] = []
    for name in _settings.sinks():
        if name == "stdout":
            sinks.append(ConsoleSink())
        elif name == "file":
            sinks.append(FileSink(_settings.ALERT_FILE_PATH))
        elif name == "webhook":
            for url in _settings.webhook_urls():
                sinks.append(WebhookSink(url, _settings.ALERT_RETRY_MAX, _settings.ALERT_RETRY_BACKOFF_MS))
    return sinks

SINKS = _build_sinks()

async def maybe_alert(key: str, payload: dict) -> None:
    """
    key = (ip_hash|reason) gibi bir şey olsun.
    - global cooldown
    - per-key dedup window
    """
    global _last_global_send
    now = time.time()

    # global cooldown
    if now - _last_global_send < _settings.ALERT_COOLDOWN_GLOBAL_SEC:
        return

    # per-key dedup
    last = _last_key_send.get(key, 0.0)
    if now - last < _settings.ALERT_DEDUP_WINDOW_SEC:
        return

    _last_global_send = now
    _last_key_send[key] = now

    for s in SINKS:
        try:
            await s.send(payload)
        except Exception:
            # yut, proje demoları için kritik değil
            pass