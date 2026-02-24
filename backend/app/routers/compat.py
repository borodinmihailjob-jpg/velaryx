import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas, star_payments
from ..config import settings
from ..database import get_db
from ..dependencies import current_user_dep
from ..limiter import limiter
from ..services import get_sun_sign

router = APIRouter(prefix="/v1/compat", tags=["compat"])
logger = logging.getLogger("astrobot.compat")


@router.post("/free")
@limiter.limit("10/minute")
async def compat_free(
    request: Request,
    payload: schemas.CompatFreeRequest,
    user: models.User = Depends(current_user_dep),
):
    """Calculate free compatibility between two people.

    Computes sun signs from birth dates, then enqueues an ARQ job for LLM interpretation.
    Returns {"status": "pending", "task_id": "..."} — client polls /v1/tasks/{task_id}.
    Result shape: {"type": "compat_free", "compat_type": str, "person_1": {...}, "person_2": {...}, "result": {...}}
    """
    sign_1 = get_sun_sign(payload.birth_date_1)
    sign_2 = get_sun_sign(payload.birth_date_2)

    logger.info(
        "Compat free | user_tg_id=%s | type=%s | sign1=%s | sign2=%s",
        user.tg_user_id,
        payload.compat_type.value,
        sign_1,
        sign_2,
    )

    arq_pool = getattr(request.app.state, "arq_pool", None)
    if arq_pool is None:
        raise HTTPException(status_code=503, detail="Очередь задач недоступна")

    job = await arq_pool.enqueue_job(
        "task_generate_compat_free",
        user_id=user.id,
        tg_user_id=user.tg_user_id,
        compat_type=payload.compat_type.value,
        sign_1=sign_1,
        sign_2=sign_2,
        name_1=payload.name_1,
        name_2=payload.name_2,
    )
    logger.info("Compat free LLM enqueued | user_id=%s | job_id=%s", user.id, job.job_id)
    return {"status": "pending", "task_id": job.job_id}


@router.post("/premium")
@limiter.limit("5/minute")
async def compat_premium(
    request: Request,
    payload: schemas.CompatFreeRequest,
    payment_id: UUID | None = None,
    use_wallet: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    """Premium compatibility report via OpenRouter Gemini.

    Requires Stars payment or wallet balance. Enqueues ARQ background job.
    Returns {"status": "pending", "task_id": "..."} — client polls /v1/tasks/{task_id}.
    Result shape: {"type": "compat_premium", "compat_type": str, "person_1": {...}, "person_2": {...},
                   "compatibility_score": int, "summary": str, "green_flags": [...], "red_flags": [...],
                   "communication_tips": [...], "time_windows": [...], "follow_up_questions": [...]}
    """
    if not settings.openrouter_api_key:
        raise HTTPException(status_code=503, detail="Премиум LLM не настроен")

    arq_pool = getattr(request.app.state, "arq_pool", None)
    if arq_pool is None:
        raise HTTPException(status_code=503, detail="Очередь задач недоступна")

    sign_1 = get_sun_sign(payload.birth_date_1)
    sign_2 = get_sun_sign(payload.birth_date_2)

    logger.info(
        "Compat premium | user_tg_id=%s | type=%s | sign1=%s | sign2=%s",
        user.tg_user_id,
        payload.compat_type.value,
        sign_1,
        sign_2,
    )

    access_claim = star_payments.claim_premium_access(
        db,
        user=user,
        feature="compat_premium",
        payment_id=payment_id,
        use_wallet=use_wallet,
    )
    try:
        job = await arq_pool.enqueue_job(
            "task_generate_compat_premium",
            user_id=user.id,
            tg_user_id=user.tg_user_id,
            compat_type=payload.compat_type.value,
            sign_1=sign_1,
            sign_2=sign_2,
            name_1=payload.name_1,
            name_2=payload.name_2,
        )
    except Exception:
        star_payments.restore_premium_access_claim(db, user=user, claim=access_claim)
        raise
    star_payments.attach_premium_claim_task(db, user=user, claim=access_claim, task_id=job.job_id)
    logger.info("Compat premium LLM enqueued | user_id=%s | job_id=%s", user.id, job.job_id)
    return {"status": "pending", "task_id": job.job_id}
