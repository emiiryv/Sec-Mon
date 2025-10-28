from time import time
from collections import defaultdict

SENSITIVE_PROBES = [
    "/.env",
    "/admin",
    "/phpinfo",
    "/wp-admin",
    "/etc/passwd",
]

RATE_WINDOW_SEC = 10.0
RATE_MAX_REQUESTS = 20

# ip -> [ts...]
ip_rate_history = defaultdict(list)

def detect_suspicious_reasons(ip_hash: str, path: str, user_agent: str | None) -> list[str]:
    reasons: list[str] = []

    lowered = path.lower()
    for probe in SENSITIVE_PROBES:
        if probe in lowered:
            reasons.append("path_scan")
            break

    if not user_agent or not user_agent.strip():
        reasons.append("bad_ua")
    elif "curl" in user_agent.lower():
        reasons.append("suspicious_ua")

    now = time()
    ip_rate_history[ip_hash].append(now)
    recent = [t for t in ip_rate_history[ip_hash] if now - t <= RATE_WINDOW_SEC]
    ip_rate_history[ip_hash] = recent
    if len(recent) > RATE_MAX_REQUESTS:
        reasons.append("rate_abuse")

    return reasons