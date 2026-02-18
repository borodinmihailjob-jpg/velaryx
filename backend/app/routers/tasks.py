"""Task status endpoint for ARQ background jobs."""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from ..dependencies import current_user_dep
from .. import models, schemas

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])
logger = logging.getLogger("astrobot.tasks")


@router.get("/{task_id}", response_model=schemas.TaskStatusResponse)
async def get_task_status(
    task_id: str,
    request: Request,
    user: models.User = Depends(current_user_dep),
):
    """Poll the status of a background LLM task."""
    # task_id is validated as a non-empty string already via path
    if not task_id or len(task_id) > 128:
        raise HTTPException(status_code=400, detail="Invalid task_id")

    pool = getattr(request.app.state if request else None, "arq_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Task queue unavailable")

    task_key = f"arq_task:{task_id}"
    try:
        raw = await pool.get(task_key)
    except Exception as exc:
        logger.warning("Redis read failed for task_key=%s: %s", task_key, exc)
        raise HTTPException(status_code=503, detail="Task queue unavailable")

    if raw is None:
        return schemas.TaskStatusResponse(status="pending")

    try:
        payload = json.loads(raw)
    except Exception:
        return schemas.TaskStatusResponse(status="failed", error="Invalid task payload")

    status = payload.get("status", "pending")
    result = payload.get("result")
    error = payload.get("error")

    return schemas.TaskStatusResponse(status=status, result=result, error=error)
