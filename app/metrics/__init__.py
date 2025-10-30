# app/metrics/__init__.py
import builtins
from prometheus_client import REGISTRY as _DEFAULT_REGISTRY, Counter, Gauge

_KEY = "_secmon_metrics_singleton_v3"

if hasattr(builtins, _KEY):
    _store = getattr(builtins, _KEY)
    METRICS_REGISTRY = _store["registry"]
    SUSPICIOUS_REQUESTS = _store["suspicious"]
    QUARANTINED_BLOCKS = _store["blocked"]
    QUARANTINED_IP_COUNT = _store["ipcount"]
else:
    METRICS_REGISTRY = _DEFAULT_REGISTRY
    SUSPICIOUS_REQUESTS = Counter(
        "suspicious_requests_total",
        "Requests observed by quarantine middleware",
        ["client"],
        registry=METRICS_REGISTRY,
    )
    QUARANTINED_BLOCKS = Counter(
        "quarantined_blocks_total",
        "Requests blocked by quarantine middleware",
        ["client"],
        registry=METRICS_REGISTRY,
    )
    QUARANTINED_IP_COUNT = Gauge(
        "quarantined_ip_count",
        "Currently quarantined unique clients",
        registry=METRICS_REGISTRY,
    )
    SUSPICIOUS_REQUESTS.labels(client="init").inc(0)
    QUARANTINED_BLOCKS.labels(client="init").inc(0)
    QUARANTINED_IP_COUNT.set(0)

    setattr(
        builtins,
        _KEY,
        dict(
            registry=METRICS_REGISTRY,
            suspicious=SUSPICIOUS_REQUESTS,
            blocked=QUARANTINED_BLOCKS,
            ipcount=QUARANTINED_IP_COUNT,
        ),
    )

def get_metrics() -> dict:
    return {
        "registry": METRICS_REGISTRY,
        "suspicious": SUSPICIOUS_REQUESTS,
        "blocked": QUARANTINED_BLOCKS,
        "ipcount": QUARANTINED_IP_COUNT,
    }