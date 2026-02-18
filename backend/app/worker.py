"""ARQ worker: async LLM tasks executed outside the HTTP request cycle."""
from __future__ import annotations

import json
import logging
from typing import Any

from arq.connections import RedisSettings

from .config import settings
from .llm_engine import (
    interpret_natal_sections_async,
    interpret_forecast_stories_async,
)

logger = logging.getLogger("astrobot.worker")

ARQ_TASK_TTL = 600  # 10 minutes — long enough for frontend polling


async def task_generate_natal(
    ctx: dict[str, Any],
    *,
    user_id: int,
    chart_id: str,
    profile_id: str,
    sun_sign: str,
    moon_sign: str,
    rising_sign: str,
    wheel_chart_url: str | None,
    created_at: str,
    natal_summary: str,
    key_aspects: list[str],
    planetary_profile: list[str],
    house_cusps: list[str],
    planets_in_houses: list[str],
    mc_line: str,
    nodes_line: str,
    house_rulers: list[str],
    dispositors: list[str],
    essential_dignities: list[str],
    configurations: list[str],
    full_aspects: list[str],
    static_sections_json: str,  # pre-built fallback sections from _build_natal_sections
) -> dict[str, Any]:
    job_id: str = ctx["job_id"]
    redis = ctx["redis"]

    logger.info("Worker: task_generate_natal start | user_id=%s | job_id=%s", user_id, job_id)

    llm_sections = await interpret_natal_sections_async(
        sun_sign=sun_sign,
        moon_sign=moon_sign,
        rising_sign=rising_sign,
        natal_summary=natal_summary,
        key_aspects=key_aspects,
        planetary_profile=planetary_profile,
        house_cusps=house_cusps,
        planets_in_houses=planets_in_houses,
        mc_line=mc_line,
        nodes_line=nodes_line,
        house_rulers=house_rulers,
        dispositors=dispositors,
        essential_dignities=essential_dignities,
        configurations=configurations,
        full_aspects=full_aspects,
    )

    # Use LLM sections if generated, otherwise static fallback
    if llm_sections:
        logger.info("Worker: natal LLM success | user_id=%s | job_id=%s", user_id, job_id)
        # Also persist to the natal LLM cache so next request is instant
        try:
            from .services import (
                _natal_llm_cache_key,
                _normalize_llm_sections,
                NATAL_LLM_CACHE_TTL_SECONDS,
                _natal_llm_cache_fingerprint,
                _extract_natal_material,
            )
        except ImportError:
            pass
        final_sections: list[dict] = [{"key": k, "text": v} for k, v in llm_sections.items()]
    else:
        logger.warning("Worker: natal LLM failed, using static fallback | user_id=%s | job_id=%s", user_id, job_id)
        try:
            static_sections: list[dict] = json.loads(static_sections_json)
        except Exception:
            static_sections = []
        final_sections = static_sections

    result = {
        "id": chart_id,
        "profile_id": profile_id,
        "sun_sign": sun_sign,
        "moon_sign": moon_sign,
        "rising_sign": rising_sign,
        "interpretation_sections": final_sections,
        "wheel_chart_url": wheel_chart_url,
        "created_at": created_at,
    }

    task_key = f"arq_task:{job_id}"
    task_payload = json.dumps({"status": "done", "result": result}, ensure_ascii=False)
    await redis.setex(task_key, ARQ_TASK_TTL, task_payload)
    logger.info("Worker: task_generate_natal done | user_id=%s | job_id=%s", user_id, job_id)
    return result


async def task_generate_stories(
    ctx: dict[str, Any],
    *,
    user_id: int,
    forecast_date: str,
    energy_score: int,
    sun_sign: str,
    moon_sign: str,
    rising_sign: str,
    mood: str,
    focus: str,
    natal_summary: str,
    key_aspects: list[str],
    fallback_slides_json: str,  # pre-built static fallback
    llm_provider_label: str | None,
) -> dict[str, Any]:
    job_id: str = ctx["job_id"]
    redis = ctx["redis"]

    logger.info("Worker: task_generate_stories start | user_id=%s | job_id=%s", user_id, job_id)

    llm_slides = await interpret_forecast_stories_async(
        sun_sign=sun_sign,
        moon_sign=moon_sign,
        rising_sign=rising_sign,
        energy_score=energy_score,
        mood=mood,
        focus=focus,
        natal_summary=natal_summary,
        key_aspects=key_aspects,
    )

    if llm_slides:
        logger.info("Worker: stories LLM success | user_id=%s | job_id=%s", user_id, job_id)
        slides = llm_slides
        provider = llm_provider_label
    else:
        logger.warning("Worker: stories LLM failed, using static fallback | user_id=%s | job_id=%s", user_id, job_id)
        try:
            slides = json.loads(fallback_slides_json)
        except Exception:
            slides = []
        provider = "local:fallback"

    result = {
        "date": forecast_date,
        "slides": slides,
        "llm_provider": provider,
    }

    task_key = f"arq_task:{job_id}"
    task_payload = json.dumps({"status": "done", "result": result}, ensure_ascii=False)
    await redis.setex(task_key, ARQ_TASK_TTL, task_payload)
    logger.info("Worker: task_generate_stories done | user_id=%s | job_id=%s", user_id, job_id)
    return result


async def on_worker_startup(ctx: dict[str, Any]) -> None:
    logger.info("ARQ worker started")


async def on_worker_shutdown(ctx: dict[str, Any]) -> None:
    logger.info("ARQ worker shutting down")


class WorkerSettings:
    functions = [task_generate_natal, task_generate_stories]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = on_worker_startup
    on_shutdown = on_worker_shutdown
    max_tries = 1  # LLM calls are expensive; don't retry automatically
    job_timeout = 120  # 2 minutes max per job
