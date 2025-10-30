from fastapi import APIRouter
import os

router = APIRouter()

@router.get("/_debug/config")
def debug_config():
    # Güvenli şekilde sadece ilgili env anahtarlarını dökelim
    def pick(prefixes):
        out = {}
        for k, v in os.environ.items():
            if any(k.startswith(p) for p in prefixes):
                out[k] = v
        return out

    return {
        "env": pick(["QUARANTINE_", "RATE_", "ZSCORE_", "APP_ENV"]),
        "note": "Do not expose this in production without auth.",
    }

@router.get("/version")
def version():
    return {"app": "Sec-Mon", "version": os.getenv("APP_VERSION", "0.1.0")}