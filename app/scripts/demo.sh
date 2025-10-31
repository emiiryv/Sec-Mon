

#!/usr/bin/env bash
set -euo pipefail

# Basit demo akışı: normal trafik -> spike (anomali/alert) -> kısa bekleme
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
IP="${IP:-198.51.100.23}"

echo "[demo] warmup + baseline..."
python app/scripts/generate_traffic.py \
  --base-url "$BASE_URL" \
  --ip "$IP" \
  --warmup-buckets 3 \
  --baseline-rps 1 --baseline-sec 6 --baseline-jitter 0.6 \
  --spike-rps 30 --spike-sec 5

echo "[demo] alerts (son 50):"
curl -s "$BASE_URL/_debug/alerts?limit=50" | jq '.'

echo "[demo] metrics (zscore & latency özet):"
curl -s "$BASE_URL/metrics" | awk '/zscore_anomaly_total|^# TYPE request_latency_seconds/{print;getline;print}'

echo "[demo] bitti."