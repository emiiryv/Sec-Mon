from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/_debug/alerts")
async def list_recent_alerts(request: Request, limit: int = 50):
    am = getattr(request.app.state, "alerts", None)
    if am is None:
        return []
    try:
        return am.recent(limit=limit)
    except Exception:
        return []
