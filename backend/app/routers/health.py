from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"ok": True, "timestamp": datetime.now(timezone.utc).isoformat()}
