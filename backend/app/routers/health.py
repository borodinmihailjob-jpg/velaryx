from datetime import datetime, timezone

from fastapi import APIRouter, Request

from ..limiter import limiter

router = APIRouter(tags=["health"])


@router.get("/health")
@limiter.limit("60/minute")
def health(request: Request):
    return {"ok": True, "timestamp": datetime.now(timezone.utc).isoformat()}
