import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..config import settings
from ..database import get_db
from ..dependencies import current_user_dep
from ..limiter import limiter

router = APIRouter(prefix="/v1/natal", tags=["natal"])
logger = logging.getLogger("astrobot.natal")


@router.post("/profile", response_model=schemas.BirthProfileResponse)
def create_profile(
    payload: schemas.BirthProfileCreateRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    logger.info(
        "Ввод данных натала | user_tg_id=%s | дата=%s | время=%s | место=%s | lat=%.5f | lon=%.5f | tz=%s",
        user.tg_user_id,
        payload.birth_date,
        payload.birth_time,
        payload.birth_place,
        payload.latitude,
        payload.longitude,
        payload.timezone,
    )
    profile = services.create_birth_profile(
        db=db,
        user_id=user.id,
        birth_date=payload.birth_date,
        birth_time=payload.birth_time,
        birth_place=payload.birth_place,
        latitude=payload.latitude,
        longitude=payload.longitude,
        timezone_name=payload.timezone,
    )
    return schemas.BirthProfileResponse(
        id=profile.id,
        birth_date=profile.birth_date,
        birth_time=profile.birth_time,
        birth_place=profile.birth_place,
        latitude=profile.latitude,
        longitude=profile.longitude,
        timezone=profile.timezone,
    )


@router.delete("/profile", response_model=schemas.ProfileDeleteResponse)
def delete_profile(
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    tg_user_id = user.tg_user_id
    stats = services.delete_user_profile_data(db=db, user_id=user.id)
    logger.info(
        "Полный сброс профиля пользователя | user_tg_id=%s | removed=%s",
        tg_user_id,
        stats,
    )
    return schemas.ProfileDeleteResponse(
        deleted_user=bool(stats["deleted_user"]),
        deleted_birth_profiles=int(stats["deleted_birth_profiles"]),
        deleted_natal_charts=int(stats["deleted_natal_charts"]),
        deleted_daily_forecasts=int(stats["deleted_daily_forecasts"]),
        deleted_tarot_sessions=int(stats["deleted_tarot_sessions"]),
        deleted_tarot_cards=int(stats["deleted_tarot_cards"]),
    )


@router.get("/profile/latest", response_model=schemas.BirthProfileResponse)
def get_latest_profile(
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    profile = services.get_latest_birth_profile(db=db, user_id=user.id)
    return schemas.BirthProfileResponse(
        id=profile.id,
        birth_date=profile.birth_date,
        birth_time=profile.birth_time,
        birth_place=profile.birth_place,
        latitude=profile.latitude,
        longitude=profile.longitude,
        timezone=profile.timezone,
    )


@router.post("/calculate", response_model=schemas.NatalChartResponse)
@limiter.limit("5/minute")
def calculate_natal(
    request: Request,
    payload: schemas.NatalCalculateRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    logger.info(
        "Запуск расчёта натальной карты | user_tg_id=%s | profile_id=%s",
        user.tg_user_id,
        payload.profile_id,
    )
    chart = services.calculate_and_store_natal_chart(db=db, user_id=user.id, profile_id=payload.profile_id)
    return schemas.NatalChartResponse(
        id=chart.id,
        profile_id=chart.profile_id,
        sun_sign=chart.sun_sign,
        moon_sign=chart.moon_sign,
        rising_sign=chart.rising_sign,
        chart_payload=chart.chart_payload,
        created_at=chart.created_at,
    )


@router.get("/latest", response_model=schemas.NatalChartResponse)
def get_latest_natal(
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    chart = services.get_latest_natal_chart(db=db, user_id=user.id)
    return schemas.NatalChartResponse(
        id=chart.id,
        profile_id=chart.profile_id,
        sun_sign=chart.sun_sign,
        moon_sign=chart.moon_sign,
        rising_sign=chart.rising_sign,
        chart_payload=chart.chart_payload,
        created_at=chart.created_at,
    )


@router.get("/full")
@limiter.limit("10/minute")
async def get_full_natal(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    """Return full natal chart with LLM interpretation.

    Fast path (cache hit): returns NatalFullResponse immediately.
    Slow path (no cache, ARQ available): enqueues background LLM job, returns
    {"status": "pending", "task_id": "..."} — client should poll /v1/tasks/{task_id}.
    Fallback (ARQ unavailable): calls LLM synchronously (legacy).
    """
    arq_pool = getattr(request.app.state, "arq_pool", None)

    # Sync DB + cache operations (fast — ms-level blocking acceptable in async route)
    chart = services.get_latest_natal_chart(db=db, user_id=user.id)
    chart_payload = chart.chart_payload if isinstance(chart.chart_payload, dict) else {}

    material = services._extract_natal_material(
        chart_payload=chart_payload,
        sun_sign=str(chart.sun_sign or ""),
        moon_sign=str(chart.moon_sign or ""),
        rising_sign=str(chart.rising_sign or ""),
    )
    fingerprint = services._natal_llm_cache_fingerprint(
        material=material,
        sun_sign=str(chart.sun_sign or ""),
        moon_sign=str(chart.moon_sign or ""),
        rising_sign=str(chart.rising_sign or ""),
    )

    # Fast path: LLM sections already cached
    cached = services._get_cached_natal_llm_sections(user_id=user.id, fingerprint=fingerprint)
    if cached:
        sections = services._build_natal_sections(material=material, llm_sections=cached)
        wheel_url = chart_payload.get("wheel_chart_url") or None
        if isinstance(wheel_url, str):
            wheel_url = wheel_url.strip() or None
        return schemas.NatalFullResponse(
            id=chart.id,
            profile_id=chart.profile_id,
            sun_sign=chart.sun_sign,
            moon_sign=chart.moon_sign,
            rising_sign=chart.rising_sign,
            chart_payload=chart_payload,
            interpretation_sections=sections,
            wheel_chart_url=wheel_url,
            created_at=chart.created_at,
        )

    # No cache — try ARQ async path
    if arq_pool is not None:
        static_sections = services._build_natal_sections(material=material, llm_sections=None)
        job = await arq_pool.enqueue_job(
            "task_generate_natal",
            user_id=user.id,
            chart_id=str(chart.id),
            profile_id=str(chart.profile_id),
            sun_sign=str(chart.sun_sign or ""),
            moon_sign=str(chart.moon_sign or ""),
            rising_sign=str(chart.rising_sign or ""),
            wheel_chart_url=chart_payload.get("wheel_chart_url") or None,
            created_at=chart.created_at.isoformat(),
            natal_summary=str(material.get("natal_summary") or ""),
            key_aspects=list(material.get("key_aspects_lines") or []),
            planetary_profile=list(material.get("planetary_profile_lines") or []),
            house_cusps=list(material.get("house_cusp_lines") or []),
            planets_in_houses=list(material.get("planets_in_houses_lines") or []),
            mc_line=str(material.get("mc_line") or ""),
            nodes_line=str(material.get("nodes_line") or ""),
            house_rulers=list(material.get("house_rulers_lines") or []),
            dispositors=list(material.get("dispositors_lines") or []),
            essential_dignities=list(material.get("dignity_lines") or []),
            configurations=list(material.get("configurations_lines") or []),
            full_aspects=list(material.get("full_aspect_lines") or []),
            static_sections_json=json.dumps(static_sections, ensure_ascii=False),
        )
        logger.info("Natal chart LLM enqueued | user_id=%s | job_id=%s", user.id, job.job_id)
        return JSONResponse({"status": "pending", "task_id": job.job_id})

    # Fallback: ARQ unavailable — synchronous LLM (legacy behavior)
    logger.warning("ARQ unavailable, falling back to sync LLM for natal | user_id=%s", user.id)
    chart, sections, wheel_chart_url = services.get_full_natal_chart(db=db, user_id=user.id)
    return schemas.NatalFullResponse(
        id=chart.id,
        profile_id=chart.profile_id,
        sun_sign=chart.sun_sign,
        moon_sign=chart.moon_sign,
        rising_sign=chart.rising_sign,
        chart_payload=chart.chart_payload,
        interpretation_sections=sections,
        wheel_chart_url=wheel_chart_url,
        created_at=chart.created_at,
    )


@router.get("/full/premium")
@limiter.limit("5/minute")
async def get_full_natal_premium(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    """Premium natal chart via OpenRouter Gemini.

    Always enqueues an ARQ background job and returns
    {"status": "pending", "task_id": "..."} — client polls /v1/tasks/{task_id}.
    Result shape: {"type": "natal_premium", "sun_sign", "moon_sign", "rising_sign",
                   "report": {...13 keys...}, "wheel_chart_url", "created_at"}
    """
    if not settings.openrouter_api_key:
        raise HTTPException(status_code=503, detail="Premium LLM not configured")

    arq_pool = getattr(request.app.state, "arq_pool", None)
    if arq_pool is None:
        raise HTTPException(status_code=503, detail="Task queue unavailable")

    chart = services.get_latest_natal_chart(db=db, user_id=user.id)
    chart_payload = chart.chart_payload if isinstance(chart.chart_payload, dict) else {}

    material = services._extract_natal_material(
        chart_payload=chart_payload,
        sun_sign=str(chart.sun_sign or ""),
        moon_sign=str(chart.moon_sign or ""),
        rising_sign=str(chart.rising_sign or ""),
    )

    job = await arq_pool.enqueue_job(
        "task_generate_natal_premium",
        user_id=user.id,
        chart_id=str(chart.id),
        profile_id=str(chart.profile_id),
        sun_sign=str(chart.sun_sign or ""),
        moon_sign=str(chart.moon_sign or ""),
        rising_sign=str(chart.rising_sign or ""),
        wheel_chart_url=chart_payload.get("wheel_chart_url") or None,
        created_at=chart.created_at.isoformat(),
        natal_summary=str(material.get("natal_summary") or ""),
        key_aspects=list(material.get("key_aspects_lines") or []),
        planetary_profile=list(material.get("planetary_profile_lines") or []),
        house_cusps=list(material.get("house_cusp_lines") or []),
        planets_in_houses=list(material.get("planets_in_houses_lines") or []),
        mc_line=str(material.get("mc_line") or ""),
        nodes_line=str(material.get("nodes_line") or ""),
        house_rulers=list(material.get("house_rulers_lines") or []),
        dispositors=list(material.get("dispositors_lines") or []),
        essential_dignities=list(material.get("dignity_lines") or []),
        configurations=list(material.get("configurations_lines") or []),
        full_aspects=list(material.get("full_aspect_lines") or []),
    )
    logger.info("Natal premium LLM enqueued | user_id=%s | job_id=%s", user.id, job.job_id)
    return JSONResponse({"status": "pending", "task_id": job.job_id})
