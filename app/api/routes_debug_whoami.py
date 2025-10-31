

from fastapi import APIRouter, Request
from app.security.ip_utils import get_client_info

router = APIRouter()

@router.get("/_debug/whoami")
async def whoami(request: Request):
    ip, ip_hash = get_client_info(request)
    return {"ip": ip, "hash": ip_hash}