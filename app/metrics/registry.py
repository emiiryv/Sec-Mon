from __future__ import annotations
import builtins
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

_KEY = "_secmon_metrics_singleton_v3"

if hasattr(builtins, _KEY):
    _store = getattr(builtins, _KEY)
    METRICS_REGISTRY = _store["registry"]
    SUSPICIOUS_REQUESTS = _store["suspicious"]
    QUARANTINED_BLOCKS = _store["blocked"]
    QUARANTINED_IP_COUNT = _store["ipcount"]
    ZSCORE_ANOMALIES = _store.get("zscore")
    REQUEST_LATENCY = _store.get("latency")
    if REQUEST_LATENCY is None:
        from prometheus_client import Histogram  # local import to avoid unused in other branch
        REQUEST_LATENCY = Histogram(
            "request_latency_seconds",
            "Request processing time in seconds",
            ["route", "method", "status"],
            registry=METRICS_REGISTRY,
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
        )
        _store["latency"] = REQUEST_LATENCY
    if ZSCORE_ANOMALIES is None:
        from prometheus_client import Counter  # local import to avoid unused in other branch
        ZSCORE_ANOMALIES = Counter(
            "zscore_anomaly_total",
            "Z-score based anomaly detections",
            ["client"],
            registry=METRICS_REGISTRY,
        )
        ZSCORE_ANOMALIES.labels(client="init").inc(0)
        _store["zscore"] = ZSCORE_ANOMALIES
else:
    METRICS_REGISTRY = CollectorRegistry()
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
    ZSCORE_ANOMALIES = Counter(
        "zscore_anomaly_total",
        "Z-score based anomaly detections",
        ["client"],
        registry=METRICS_REGISTRY,
    )
    REQUEST_LATENCY = Histogram(
        "request_latency_seconds",
        "Request processing time in seconds",
        ["route", "method", "status"],
        registry=METRICS_REGISTRY,
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )
    SUSPICIOUS_REQUESTS.labels(client="init").inc(0)
    QUARANTINED_BLOCKS.labels(client="init").inc(0)
    QUARANTINED_IP_COUNT.set(0)
    ZSCORE_ANOMALIES.labels(client="init").inc(0)
    setattr(
        builtins,
        _KEY,
        dict(
            registry=METRICS_REGISTRY,
            suspicious=SUSPICIOUS_REQUESTS,
            blocked=QUARANTINED_BLOCKS,
            ipcount=QUARANTINED_IP_COUNT,
            zscore=ZSCORE_ANOMALIES,
            latency=REQUEST_LATENCY,
        ),
    )


def get_metrics() -> dict[str, object]:
    return {
        "registry": METRICS_REGISTRY,
        "suspicious": SUSPICIOUS_REQUESTS,
        "blocked": QUARANTINED_BLOCKS,
        "ipcount": QUARANTINED_IP_COUNT,
        "zscore": ZSCORE_ANOMALIES,
        "latency": REQUEST_LATENCY,
    }