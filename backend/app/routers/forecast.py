import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..database import get_db
from ..dependencies import current_user_dep
from ..limiter import limiter
from ..llm_engine import llm_provider_label

router = APIRouter(prefix="/v1/forecast", tags=["forecast"])
logger = logging.getLogger("astrobot.forecast")


@router.get("/daily", response_model=schemas.ForecastDailyResponse)
def get_daily_forecast(
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    forecast = services.get_or_create_daily_forecast(
        db=db,
        user_id=user.id,
        forecast_date=date.today(),
    )
    return schemas.ForecastDailyResponse(
        date=forecast.forecast_date,
        energy_score=forecast.energy_score,
        summary=forecast.summary,
        payload=forecast.payload,
    )


@router.get("/stories")
@limiter.limit("10/minute")
async def get_forecast_stories(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    """Return daily story slides with LLM interpretation.

    ARQ path: enqueues background LLM job, returns {"status":"pending","task_id":"..."}.
    Fallback: synchronous LLM when ARQ unavailable.
    """
    arq_pool = getattr(request.app.state, "arq_pool", None)

    chart = services.get_latest_natal_chart(db=db, user_id=user.id)
    forecast = services.get_or_create_daily_forecast(
        db=db,
        user_id=user.id,
        forecast_date=date.today(),
    )

    interpretation: dict = {}
    if isinstance(chart.chart_payload, dict):
        interpretation = chart.chart_payload.get("interpretation", {}) or {}

    aspects_list: list[str] = []
    raw_aspects = interpretation.get("key_aspects")
    if isinstance(raw_aspects, list):
        for item in raw_aspects[:4]:
            text = str(item).strip()
            if text:
                aspects_list.append(text)

    forecast_payload = forecast.payload if isinstance(forecast.payload, dict) else {}
    mood = str(forecast_payload.get("mood") or "баланс")
    focus = str(forecast_payload.get("focus") or "приоритетах")
    natal_summary = str(interpretation.get("summary") or "").strip()

    if arq_pool is not None:
        static_fallback = services._build_fallback_story_slides(
            chart=chart, forecast=forecast, interpretation=interpretation
        )
        job = await arq_pool.enqueue_job(
            "task_generate_stories",
            user_id=user.id,
            forecast_date=forecast.forecast_date.isoformat(),
            energy_score=int(forecast.energy_score or 0),
            sun_sign=str(chart.sun_sign or ""),
            moon_sign=str(chart.moon_sign or ""),
            rising_sign=str(chart.rising_sign or ""),
            mood=mood,
            focus=focus,
            natal_summary=natal_summary,
            key_aspects=aspects_list,
            fallback_slides_json=json.dumps(static_fallback, ensure_ascii=False),
            llm_provider_label=llm_provider_label(),
            mbti_type=user.mbti_type,
        )
        logger.info("Stories LLM enqueued | user_id=%s | job_id=%s", user.id, job.job_id)
        return JSONResponse({"status": "pending", "task_id": job.job_id})

    # Fallback: ARQ unavailable — synchronous LLM (legacy)
    logger.warning("ARQ unavailable, falling back to sync LLM for stories | user_id=%s", user.id)
    slides, provider = services.build_forecast_story_slides(chart=chart, forecast=forecast)
    return schemas.ForecastStoriesResponse(
        date=forecast.forecast_date,
        slides=[schemas.ForecastStorySlide(**slide) for slide in slides],
        llm_provider=provider,
    )
