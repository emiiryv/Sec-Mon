#!/usr/bin/env bash
set -euo pipefail

URL="${1:-http://127.0.0.1:8000/health}"
N="${N:-256}"
P="${P:-32}"

echo "[boom] Hitting $URL with $N requests (parallel=$P)"
seq "$N" | xargs -P "$P" -I{} curl -s "$URL" >/dev/null || true

echo "[boom] sample metrics:"
curl -s http://127.0.0.1:8000/metrics | grep -E 'quarantined_ip_count|suspicious_requests_total|quarantined_blocks_total'