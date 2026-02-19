import logging
from datetime import date as date_type

from fastapi import APIRouter, Depends, Request

from .. import models, schemas
from ..dependencies import current_user_dep
from ..limiter import limiter
from ..llm_engine import _sanitize_user_input
from ..numerology_engine import calculate_all

router = APIRouter(prefix="/v1/numerology", tags=["numerology"])
logger = logging.getLogger("astrobot.numerology")


@router.post("/calculate", response_model=schemas.NumerologyCalculateResponse)
@limiter.limit("10/minute")
async def calculate_numerology(
    request: Request,
    payload: schemas.NumerologyCalculateRequest,
    user: models.User = Depends(current_user_dep),
):
    """Calculate all 6 numerology numbers immediately (pure Python), then enqueue
    an ARQ job for LLM interpretation.

    Returns numbers instantly plus a task_id to poll for interpretations.
    """
    logger.info(
        "Numerology calculate | user_tg_id=%s | birth_date=%s",
        user.tg_user_id,
        payload.birth_date,
    )

    today = date_type.today()
    result = calculate_all(
        full_name=payload.full_name,
        birth_date=payload.birth_date,
        current_date=today,
    )
    numbers = schemas.NumerologyNumbers(**result.to_dict())

    arq_pool = getattr(request.app.state, "arq_pool", None)
    if arq_pool is not None:
        safe_name = _sanitize_user_input(payload.full_name, max_length=200)
        job = await arq_pool.enqueue_job(
            "task_generate_numerology",
            user_id=user.id,
            full_name=safe_name,
            birth_date=payload.birth_date.isoformat(),
            current_date=today.isoformat(),
            life_path=result.life_path,
            expression=result.expression,
            soul_urge=result.soul_urge,
            personality=result.personality,
            birthday=result.birthday,
            personal_year=result.personal_year,
        )
        logger.info(
            "Numerology LLM enqueued | user_id=%s | job_id=%s",
            user.id,
            job.job_id,
        )
        return schemas.NumerologyCalculateResponse(
            numbers=numbers,
            status="pending",
            task_id=job.job_id,
        )

    logger.warning("ARQ unavailable, numerology without LLM | user_id=%s", user.id)
    return schemas.NumerologyCalculateResponse(
        numbers=numbers,
        status="done",
        task_id=None,
    )
