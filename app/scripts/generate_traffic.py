

import argparse, asyncio, time, random
import httpx

async def phase(client, url: str, rps: float, dur_s: float, xff: str | None, jitter: float = 0.0):
    t_end = time.time() + dur_s
    while time.time() < t_end:
        headers = {}
        if xff:
            headers["X-Forwarded-For"] = xff
        try:
            await client.get(f"{url}/health", headers=headers, timeout=3.0)
        except Exception:
            pass
        j = 1.0
        if jitter > 0.0:
            # ±jitter oranında rps dalgalansın (std>0 için)
            j *= (1.0 + random.uniform(-jitter, jitter))
        eff_rps = max(rps * j, 0.01)
        await asyncio.sleep(1.0 / eff_rps)

async def warmup(client, url: str, buckets: int, xff: str | None):
    # 1,2,3,... 'buckets' kadar kovayı 1 sn aralıkla doldur (std>0)
    for hits in range(1, max(buckets, 0) + 1):
        headers = {}
        if xff:
            headers["X-Forwarded-For"] = xff
        for _ in range(hits):
            try:
                await client.get(f"{url}/health", headers=headers, timeout=3.0)
            except Exception:
                pass
        await asyncio.sleep(1.05)

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--ip", default="198.51.100.23")
    ap.add_argument("--baseline-rps", type=float, default=1.0)
    ap.add_argument("--baseline-sec", type=float, default=10.0)
    ap.add_argument("--baseline-jitter", type=float, default=0.0, help="0.0-1.0 arası oransal jitter")
    ap.add_argument("--warmup-buckets", type=int, default=0, help="Warmup kova sayısı (1,2,3,... gönderir)")
    ap.add_argument("--spike-rps", type=float, default=30.0)
    ap.add_argument("--spike-sec", type=float, default=5.0)
    args = ap.parse_args()
    async with httpx.AsyncClient() as client:
        if args.warmup_buckets > 0:
            await warmup(client, args.base_url, args.warmup_buckets, args.ip)
        await phase(client, args.base_url, args.baseline_rps, args.baseline_sec, args.ip, jitter=args.baseline_jitter)
        await phase(client, args.base_url, args.spike_rps, args.spike_sec, args.ip, jitter=0.0)

if __name__ == "__main__":
    asyncio.run(main())