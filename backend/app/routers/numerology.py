import logging
from datetime import date as date_type
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas, star_payments
from ..config import settings
from ..database import get_db
from ..dependencies import current_user_dep
from ..history import save_report_to_history
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
    report_id = f"{user.tg_user_id}_{payload.birth_date.isoformat()}"
    await save_report_to_history(
        redis=arq_pool,
        tg_user_id=user.tg_user_id,
        report_type="numerology_basic",
        report_id=report_id,
        is_premium=False,
        summary={
            "numbers": {
                "life_path": result.life_path,
                "expression": result.expression,
                "soul_urge": result.soul_urge,
                "personality": result.personality,
                "birthday": result.birthday,
            },
        },
    )

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


@router.post("/premium")
@limiter.limit("5/minute")
async def calculate_numerology_premium(
    request: Request,
    payload: schemas.NumerologyCalculateRequest,
    payment_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    """Premium numerology report via OpenRouter Gemini.

    Calculates all 6 numbers, then enqueues an ARQ background job for deep analysis.
    Returns {"status": "pending", "task_id": "..."} — client polls /v1/tasks/{task_id}.
    Result shape: {"type": "numerology_premium", "numbers": {...}, "report": {...10 keys...}}
    """
    if not settings.openrouter_api_key:
        raise HTTPException(status_code=503, detail="Премиум LLM не настроен")

    arq_pool = getattr(request.app.state, "arq_pool", None)
    if arq_pool is None:
        raise HTTPException(status_code=503, detail="Очередь задач недоступна")

    today = date_type.today()
    result = calculate_all(
        full_name=payload.full_name,
        birth_date=payload.birth_date,
        current_date=today,
    )

    safe_name = _sanitize_user_input(payload.full_name, max_length=200)
    star_payments.claim_paid_payment_for_feature(
        db,
        user=user,
        feature="numerology_premium",
        payment_id=payment_id,
    )
    try:
        job = await arq_pool.enqueue_job(
            "task_generate_numerology_premium",
            user_id=user.id,
            tg_user_id=user.tg_user_id,
            full_name=safe_name,
            birth_date=payload.birth_date.isoformat(),
            life_path=result.life_path,
            expression=result.expression,
            soul_urge=result.soul_urge,
            personality=result.personality,
            birthday=result.birthday,
            personal_year=result.personal_year,
        )
    except Exception:
        if payment_id is not None:
            star_payments.restore_consumed_payment_to_paid(db, user=user, payment_id=payment_id)
        raise
    if payment_id is not None:
        star_payments.attach_consumed_payment_task(db, user=user, payment_id=payment_id, task_id=job.job_id)
    logger.info(
        "Numerology premium LLM enqueued | user_id=%s | job_id=%s",
        user.id,
        job.job_id,
    )
    return {"status": "pending", "task_id": job.job_id}
