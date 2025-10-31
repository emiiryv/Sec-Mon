# app/metrics/__init__.py
"""
Thin re-export layer to avoid duplicating singleton/registry logic.
All metrics are created and stored in app.metrics.registry; this module just
re-exports them for convenient imports like `from app.metrics import ...`.
"""
from .registry import (
    METRICS_REGISTRY,
    SUSPICIOUS_REQUESTS,
    QUARANTINED_BLOCKS,
    QUARANTINED_IP_COUNT,
    ZSCORE_ANOMALIES,
    REQUEST_LATENCY,
    get_metrics,
)

__all__ = [
    "METRICS_REGISTRY",
    "SUSPICIOUS_REQUESTS",
    "QUARANTINED_BLOCKS",
    "QUARANTINED_IP_COUNT",
    "ZSCORE_ANOMALIES",
    "REQUEST_LATENCY",
    "get_metrics",
]