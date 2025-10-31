from __future__ import annotations
import math, time
from typing import Deque, Tuple
from collections import deque

class ZScoreWindow:
    """
    Bucket’lı istek sayımına göre z-skoru anomali dedektörü.
    - bucket_sec: zaman kovası (s)
    - window_min: geri dönük pencere (dakika)
    - min_samples: z-skoru hesaplamak için alt sınır (n)
    - threshold: z > threshold ise anomaly
    """
    def __init__(self, bucket_sec: int, window_min: int, min_samples: int, threshold: float):
        self.bucket_sec = float(bucket_sec)
        self.window_sec = float(max(window_min, 1) * 60)
        self.min_samples = int(min_samples)
        self.threshold = float(threshold)
        self._cur_bucket_ts = 0.0
        self._cur_count = 0
        self._hist: Deque[int] = deque()  # geçmiş kovalar
        self._hist_ts: Deque[float] = deque()

    def _roll_if_needed(self, now: float):
        if self._cur_bucket_ts == 0.0:
            self._cur_bucket_ts = now
            return
        if now - self._cur_bucket_ts >= self.bucket_sec:
            # mevcut kovayı geçmişe at
            self._hist.append(self._cur_count)
            self._hist_ts.append(self._cur_bucket_ts)
            self._cur_bucket_ts = now
            self._cur_count = 0
            # pencere dışını temizle
            cutoff = now - self.window_sec
            while self._hist_ts and self._hist_ts[0] < cutoff:
                self._hist_ts.popleft()
                self._hist.popleft()

    def add_hit(self, now: float | None = None) -> Tuple[float, bool]:
        """
        Bir hit ekle ve mevcut kovayı referans alarak (geçmişe göre) z-skoru döndür.
        Return: (z, is_anomaly)
        """
        now = now or time.time()
        self._roll_if_needed(now)
        self._cur_count += 1
        return self.score(now)

    def score(self, now: float | None = None) -> Tuple[float, bool]:
        now = now or time.time()
        # güncel kova dahil edilmeden geçmişten ölç (leak önlemek için)
        samples = list(self._hist)
        n = len(samples)
        if n < self.min_samples:
            return 0.0, False
        mean = sum(samples) / n
        var = sum((x - mean) ** 2 for x in samples) / max(n - 1, 1)
        std = math.sqrt(var) if var > 0 else 0.0
        z = 0.0
        if std > 0:
            # güncel kovayı geçmişe göre kıyasla
            cur = self._cur_count
            z = (cur - mean) / std
        return z, (z > self.threshold)
