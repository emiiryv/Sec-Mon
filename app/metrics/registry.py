from __future__ import annotations
from prometheus_client import Counter, Gauge

# Şüpheli istek sayaçları (reason bazlı etiketli counter)
SUSPICIOUS_REQUESTS = Counter(
    "suspicious_requests_total",
    "Number of suspicious requests detected",
    ["ip_hash", "reason"],
)

# Karantinadaki IP sayısını anlık göstermek için gauge
QUARANTINED_IP_COUNT = Gauge(
    "quarantined_ip_count",
    "Number of currently quarantined IPs",
)