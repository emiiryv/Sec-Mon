

from fastapi import APIRouter
from time import time
try:
    # middleware içindeki global harita (timestamp tabanlı) mevcutsa kullan
    from app.security.middleware_quarantine import _quarantine as _Q  # type: ignore
except Exception:
    _Q = {}

router = APIRouter()

@router.get("/_debug/banlist")
async def banlist():
    now = time()
    out = []
    try:
        for k, ts in getattr(_Q, "items", lambda: [])():
            if float(ts) > now:
                out.append({"client": k, "expires": float(ts), "remaining": float(ts) - now})
    except Exception:
        pass
    return sorted(out, key=lambda x: x["remaining"], reverse=True)