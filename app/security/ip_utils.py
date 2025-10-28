import ipaddress
from typing import List
from fastapi import Request

def parse_cidrs(csv: str) -> List[ipaddress._BaseNetwork]:
    nets = []
    for part in (csv or "").split(","):
        p = part.strip()
        if not p:
            continue
        try:
            nets.append(ipaddress.ip_network(p, strict=False))
        except ValueError:
            pass
    return nets

def client_ip_from_xff(request: Request, trusted_proxies: List[ipaddress._BaseNetwork]) -> str:
    """
    Güvenilir proxy arkası IP çıkarımı.
    - XFF zincirindeki IP'ler soldan sağa orijinalden proxy'ye gider.
    - request.client.host en sonda (son proxy) olabilir.
    """
    xff = request.headers.get("x-forwarded-for")
    if not xff:
        return request.client.host if request.client else "unknown"
    chain = [x.strip() for x in xff.split(",") if x.strip()]
    # Zincirin sonunda genelde en yakın proxy olur; biz soldan (gerçek istemci) başlayalım.
    candidate = chain[0]
    try:
        ip_obj = ipaddress.ip_address(candidate)
    except ValueError:
        return request.client.host if request.client else "unknown"
    # Proxy kontrolü: son soket IP'si trusted mı?
    sock = request.client.host if request.client else None
    if sock:
        try:
            sock_ip = ipaddress.ip_address(sock)
            if any(sock_ip in net for net in trusted_proxies):
                return str(ip_obj)
        except ValueError:
            pass
    # Eğer güvenilir proxy değilse, soket IP'si kabul.
    return request.client.host if request.client else str(ip_obj)