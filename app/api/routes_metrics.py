from fastapi import APIRouter, Response, Request
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, REGISTRY

router = APIRouter()

@router.get("/metrics")
async def metrics(request: Request):
    # App.state’e sabitlediğimiz *aynı* registry’i eksport et
    sm = getattr(request.app.state, "secmon_metrics", None)
    reg = sm["registry"] if isinstance(sm, dict) and "registry" in sm else REGISTRY
    data = generate_latest(reg)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)