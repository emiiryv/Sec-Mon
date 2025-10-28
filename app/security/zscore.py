from collections import defaultdict, deque
from math import sqrt
from time import time
from app.core.settings import get_settings

# Proje ayarlarını içe al
_settings = get_settings()

# IP başına "bucket" başına istek sayımı (moving window)
# ip_hash -> deque of (bucket_id, count) ; bucket_id = floor(now / ZSCORE_BUCKET_SEC)
WINDOW_MIN_DEFAULT = 30

class ZScoreDetector:
    def __init__(self, window_min: int = WINDOW_MIN_DEFAULT, min_samples: int = 10, threshold: float = 3.0):
        self.window_min = window_min
        self.min_samples = min_samples
        self.threshold = threshold
        self.buckets = defaultdict(lambda: deque(maxlen=1024))  # generous cap

    def _bucket(self, epoch_seconds: float) -> int:
        size = max(1, _settings.ZSCORE_BUCKET_SEC)
        return int(epoch_seconds // size)

    def add_request_and_score(self, ip_hash: str, now_s: float | None = None) -> tuple[float | None, bool]:
        """
        İsteği say ve güncel z-skorunu dön. (score, is_anomaly)
        Bucket süresi .env'den ZSCORE_BUCKET_SEC ile kontrol edilir.
        Pencere uzunluğu dakika cinsindendir (window_min) ve bucket sayısına çevrilerek kırpılır.
        """
        if now_s is None:
            now_s = time()
        bucket = self._bucket(now_s)

        dq = self.buckets[ip_hash]
        if not dq or dq[-1][0] != bucket:
            dq.append((bucket, 1))
        else:
            m, c = dq.pop()
            dq.append((m, c + 1))

        # window kırp: window_min(dakika) → saniye → kaç bucket?
        buckets_to_keep = max(1, (self.window_min * 60) // max(1, _settings.ZSCORE_BUCKET_SEC))
        cutoff = bucket - buckets_to_keep
        while dq and dq[0][0] < cutoff:
            dq.popleft()

        counts = [c for _, c in dq]
        n = len(counts)
        if n < self.min_samples:
            return None, False

        mean = sum(counts) / n
        var = sum((x - mean) ** 2 for x in counts) / n if n > 0 else 0.0
        std = sqrt(var)
        if std == 0:
            return None, False
        z = (counts[-1] - mean) / std
        return z, z >= self.threshold