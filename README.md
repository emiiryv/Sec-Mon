# Sec-Mon (FastAPI Security Monitor)

Küçük ve net bir “fail2ban-lite” yaklaşımı: **rate window** tabanlı karantina, opsiyonel **Z-score** anomalisi, ve **Prometheus** metrikleri. Veritabanı **PostgreSQL**’dir.

## Özellikler
- 🔒 **QuarantineMiddleware**: kısa pencerede yoğun istekleri banlar.
- 📈 **Prometheus /metrics**: anlık metrikler (quarantined IP count, blocked requests, vs.).
- 🧠 **Z-score anomaly** (opsiyonel): trafikteki ani sıçramaları modelden bağımsız tespit eder.
- 🧰 **Debug endpoint**: `/_debug/config` seçili env’leri döndürür (geliştirme amaçlı).

## Gereksinimler
- Python 3.11+
- PostgreSQL 14+ (lokal ya da Docker)
- `pip` / `venv` (veya `poetry`)

## Hızlı Başlangıç
```bash
git clone <repo-url>
cd Sec-Mon

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# .env içindeki DATABASE_URL ve diğer anahtarları kendine göre düzenle

uvicorn app.main:app --reload
```

### PostgreSQL Hızlı Kurulum (lokal)
**psql ile:**
```bash
createuser -P secmon
createdb -O secmon secmon
# .env(.example) içindeki DATABASE_URL'i bu kullanıcı/şifre ile eşleştir.
```

**Docker Compose ile (opsiyonel):**
```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: secmon
      POSTGRES_USER: secmon
      POSTGRES_PASSWORD: secmon
    ports:
      - "5432:5432"
    volumes:
      - ./.pgdata:/var/lib/postgresql/data
```

## Çalıştırma
```bash
uvicorn app.main:app --reload
# App: http://127.0.0.1:8000
```

## Quickstart (Local)

```bash
cp .env.example .env
make dev           # API: http://127.0.0.1:8000
```

## Observability Stack (Prometheus + Grafana)

```bash
make obs-up
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3000  (admin/admin)
```

Grafana auto-provisioning açık; `ops/grafana/dashboard_secmon.json` otomatik yüklenir.

## Demo

```bash
make demo
# Son alert'ler:    curl -s http://127.0.0.1:8000/_debug/alerts?limit=50 | jq
# Metrikler:        curl -s http://127.0.0.1:8000/metrics | head
```

## Testler

```bash
make test
```

## Endpoint’ler
- `GET /health` — basit sağlık kontrolü.
- `GET /metrics` — Prometheus metrikleri (ana app’ten ayrı **mount**, karantinadan muaf).
- `GET /_debug/config` — seçili env’lerin görünümü (**sadece geliştirme**).

## Yapı
- `app/main.py` — FastAPI app; `/metrics` ayrı sub-app olarak mount edilir.
- `app/security/middleware_monitor.py` — istek gözlemcisi/metrik üreticisi.
- `app/security/middleware_quarantine.py` — karantina/ban mantığı.

> **Middleware sırası** önemlidir: `MonitorMiddleware` → `QuarantineMiddleware`.

## Konfigürasyon
Çevre değişkenleri `.env(.example)` dosyasında. Önemli anahtarlar:

- **Database**
  - `DATABASE_URL` — PostgreSQL bağlantısı (ör. `postgresql+asyncpg://secmon:secmon@127.0.0.1:5432/secmon`).

- **Rate Window**
  - `RATE_WINDOW_SECONDS` — pencere süresi (s).
  - `RATE_THRESHOLD` — pencere içinde izinli maksimum istek. Aşıldığında ban tetiklenir.

- **Quarantine**
  - `QUARANTINE_ENABLED` — karantina açık/kapalı.
  - `QUARANTINE_BAN_SECONDS` — ban süresi.
  - `QUARANTINE_BLOCK_STATUS` — banlıya dönen HTTP status (örn. 403).
  - `QUARANTINE_REQUIRE_Z` — ban için Z-score şartı.
  - `QUARANTINE_EXCLUDE_PATHS` — karantinadan muaf yollar (örn. `/metrics`).
  - `ALLOWLIST_IPS` — hiç banlanmayacak IP/Hash listesi.
  - `QUARANTINE_DEBUG` — geliştirme modunda detaylı log.

- **Z-Score**
  - `ZSCORE_ENABLED`, `ZSCORE_BUCKET_SEC`, `ZSCORE_WINDOW_MIN`,
    `ZSCORE_MIN_SAMPLES`, `ZSCORE_THRESHOLD`.

- **Proxy / XFF**
  - `TRUSTED_PROXY_CIDRS` — güvenilir proxy aralıkları; gerçek istemci IP’si XFF’ten alınır.

- **Günlük Saklama**
  - `RETENTION_DAYS` — veri/log saklama için üst sınır.

## Hızlı Testler
Rate/ban akışını görmek için:
```bash
# Spike yarat
seq 256 | xargs -P 32 -I{} curl -s http://127.0.0.1:8000/health >/dev/null

# Health muhtemelen 403 döner (ban süresince)
curl -i http://127.0.0.1:8000/health

# Metriklerde artış gör
curl -sL http://127.0.0.1:8000/metrics |   grep -E 'quarantined_ip_count|suspicious_requests_total|quarantined_blocks_total'
```
`/metrics` yolunun **karantinadan muaf** olduğunu doğrulamak için:
```bash
curl -sL http://127.0.0.1:8000/metrics | head
```

## Güvenlik Notları
- `/_debug/config` sadece geliştirmede açık kalsın. Prod’da kaldırın ya da koruyun.
- `.env` dosyasını asla commit etmeyin; `.env.example` paylaşılabilir şablondur.

## Lisans
TBD
