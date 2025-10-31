from __future__ import annotations
import os
import ipaddress
import hashlib
from typing import List, Tuple, Set
from fastapi import Request

# --- Back-compat helpers (kept) ----------------------------------------------

def parse_cidrs(csv: str) -> List[ipaddress._BaseNetwork]:
    """
    Parse a comma-separated CIDR list into ipaddress network objects.
    """
    nets: List[ipaddress._BaseNetwork] = []
    for part in (csv or "").split(","):
        p = part.strip()
        if not p:
            continue
        try:
            nets.append(ipaddress.ip_network(p, strict=False))
        except ValueError:
            # ignore invalid cidr token
            pass
    return nets

def client_ip_from_xff(request: Request, trusted_proxies: List[ipaddress._BaseNetwork]) -> str:
    """
    (Deprecated) Extract client IP when behind trusted proxy list provided by caller.
    Prefer using get_client_ip() which reads TRUSTED_PROXY_CIDRS from environment.
    """
    xff = request.headers.get("x-forwarded-for")
    if not xff:
        return request.client.host if request.client else "unknown"
    chain = [x.strip() for x in xff.split(",") if x.strip()]
    # take left-most as original client
    candidate = chain[0]
    try:
        ip_obj = ipaddress.ip_address(candidate)
    except ValueError:
        return request.client.host if request.client else "unknown"
    sock = request.client.host if request.client else None
    if sock:
        try:
            sock_ip = ipaddress.ip_address(sock)
            if any(sock_ip in net for net in trusted_proxies):
                return str(ip_obj)
        except ValueError:
            pass
    # fall back to socket ip if proxy is not trusted
    return request.client.host if request.client else str(ip_obj)

# --- New S3 API --------------------------------------------------------------

def _trusted_cidrs():
    s = os.getenv("TRUSTED_PROXY_CIDRS", "")
    nets: List[ipaddress._BaseNetwork] = []
    for p in s.split(","):
        p = p.strip()
        if not p:
            continue
        try:
            nets.append(ipaddress.ip_network(p))
        except Exception:
            pass
    return nets

def _is_trusted(ip: str) -> bool:
    try:
        ipobj = ipaddress.ip_address(ip)
        return any(ipobj in net for net in _trusted_cidrs())
    except Exception:
        return False

def _hash_ip(ip: str) -> str:
    salt = os.getenv("IP_SALT", "")
    return hashlib.sha256((salt + ip).encode("utf-8")).hexdigest()[:16]

def get_client_ip(request: Request) -> str:
    remote = request.client.host if request.client else ""
    xff = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if xff and _is_trusted(remote):
        first = xff.split(",")[0].strip()
        try:
            ipaddress.ip_address(first)
            return first
        except Exception:
            return remote
    return remote

def get_client_info(request: Request) -> Tuple[str, str]:
    ip = get_client_ip(request)
    return ip, _hash_ip(ip)

_ALLOW_CACHE: Set[str] | None = None

def is_allowlisted(ip: str, ip_hash: str) -> bool:
    global _ALLOW_CACHE
    if _ALLOW_CACHE is None:
        s = os.getenv("ALLOWLIST_IPS", "")
        _ALLOW_CACHE = {x.strip() for x in s.split(",") if x.strip()}
    return ip in _ALLOW_CACHE or ip_hash in _ALLOW_CACHE