"""ARQ worker: async LLM tasks executed outside the HTTP request cycle."""
from __future__ import annotations

import json
import logging
from typing import Any

from arq.connections import RedisSettings

from .config import settings
from .llm_engine import (
    interpret_natal_sections_async,
    interpret_natal_premium_async,
    interpret_forecast_stories_async,
    interpret_numerology_async,
    interpret_numerology_premium_async,
    interpret_tarot_premium_async,
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


_NUMEROLOGY_FALLBACK: dict[str, str] = {
    "life_path": (
        "Число Жизненного Пути — главный вектор вашего развития. "
        "Оно указывает на таланты, с которыми вы пришли в мир, и уроки, которые предстоит пройти. "
        "Используйте его как компас при важных выборах."
    ),
    "expression": (
        "Число Выражения отражает ваш полный потенциал, заложенный в имени. "
        "Оно показывает, как вы проявляете себя в мире и к чему стремитесь. "
        "Это ваша «зона роста» — то, что нужно развивать осознанно."
    ),
    "soul_urge": (
        "Число Души раскрывает ваши истинные желания и внутренние мотивы. "
        "То, что движет вами на уровне сердца. "
        "Согласуйте внешние цели с этим числом — и получите подлинное удовлетворение."
    ),
    "personality": (
        "Число Личности — это то, каким вас видят окружающие. "
        "Ваша внешняя маска и стиль взаимодействия с миром. "
        "Осознанное использование этой энергии помогает строить нужные связи."
    ),
    "birthday": (
        "Число Дня Рождения — дополнительный талант или особый дар. "
        "Это специфическая способность, которую вы принесли в воплощение. "
        "Опирайтесь на неё в моменты неопределённости."
    ),
    "personal_year": (
        "Число Личного Года задаёт тему текущего годичного цикла. "
        "Оно указывает, чему стоит уделить особое внимание прямо сейчас. "
        "Следование ритму личного года снижает сопротивление и ускоряет рост."
    ),
}


async def task_generate_numerology(
    ctx: dict[str, Any],
    *,
    user_id: int,
    full_name: str,
    birth_date: str,
    current_date: str,
    life_path: int,
    expression: int,
    soul_urge: int,
    personality: int,
    birthday: int,
    personal_year: int,
) -> dict[str, Any]:
    job_id: str = ctx["job_id"]
    redis = ctx["redis"]

    logger.info(
        "Worker: task_generate_numerology start | user_id=%s | job_id=%s",
        user_id,
        job_id,
    )

    llm_interpretations = await interpret_numerology_async(
        full_name=full_name,
        birth_date=birth_date,
        life_path=life_path,
        expression=expression,
        soul_urge=soul_urge,
        personality=personality,
        birthday=birthday,
        personal_year=personal_year,
    )

    if llm_interpretations:
        logger.info(
            "Worker: numerology LLM success | user_id=%s | job_id=%s",
            user_id,
            job_id,
        )
        interpretations = llm_interpretations
    else:
        logger.warning(
            "Worker: numerology LLM failed, using static fallback | user_id=%s | job_id=%s",
            user_id,
            job_id,
        )
        interpretations = _NUMEROLOGY_FALLBACK

    result = {
        "numbers": {
            "life_path": life_path,
            "expression": expression,
            "soul_urge": soul_urge,
            "personality": personality,
            "birthday": birthday,
            "personal_year": personal_year,
        },
        "interpretations": interpretations,
    }

    task_key = f"arq_task:{job_id}"
    task_payload = json.dumps({"status": "done", "result": result}, ensure_ascii=False)
    await redis.setex(task_key, ARQ_TASK_TTL, task_payload)
    logger.info(
        "Worker: task_generate_numerology done | user_id=%s | job_id=%s",
        user_id,
        job_id,
    )
    return result


async def task_generate_numerology_premium(
    ctx: dict[str, Any],
    *,
    user_id: int,
    full_name: str,
    birth_date: str,
    life_path: int,
    expression: int,
    soul_urge: int,
    personality: int,
    birthday: int,
    personal_year: int,
) -> dict[str, Any]:
    """Premium numerology report via OpenRouter Gemini. Returns rich JSON report."""
    job_id: str = ctx["job_id"]
    redis = ctx["redis"]

    logger.info("Worker: task_generate_numerology_premium start | user_id=%s | job_id=%s", user_id, job_id)

    report = await interpret_numerology_premium_async(
        full_name=full_name,
        birth_date=birth_date,
        life_path=life_path,
        expression=expression,
        soul_urge=soul_urge,
        personality=personality,
        birthday=birthday,
        personal_year=personal_year,
    )

    if report:
        logger.info("Worker: numerology premium LLM success | user_id=%s | job_id=%s", user_id, job_id)
    else:
        logger.error("Worker: numerology premium LLM failed | user_id=%s | job_id=%s", user_id, job_id)

    result = {
        "type": "numerology_premium",
        "numbers": {
            "life_path": life_path,
            "expression": expression,
            "soul_urge": soul_urge,
            "personality": personality,
            "birthday": birthday,
            "personal_year": personal_year,
        },
        "report": report,  # None if LLM failed
    }

    task_key = f"arq_task:{job_id}"
    task_payload = json.dumps({"status": "done", "result": result}, ensure_ascii=False)
    await redis.setex(task_key, ARQ_TASK_TTL, task_payload)
    logger.info("Worker: task_generate_numerology_premium done | user_id=%s | job_id=%s", user_id, job_id)
    return result


async def task_generate_natal_premium(
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
) -> dict[str, Any]:
    """Premium natal chart via OpenRouter Gemini. Returns rich JSON report."""
    job_id: str = ctx["job_id"]
    redis = ctx["redis"]

    logger.info("Worker: task_generate_natal_premium start | user_id=%s | job_id=%s", user_id, job_id)

    report = await interpret_natal_premium_async(
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

    if report:
        logger.info("Worker: natal premium LLM success | user_id=%s | job_id=%s", user_id, job_id)
    else:
        logger.error("Worker: natal premium LLM failed | user_id=%s | job_id=%s", user_id, job_id)

    result = {
        "type": "natal_premium",
        "sun_sign": sun_sign,
        "moon_sign": moon_sign,
        "rising_sign": rising_sign,
        "report": report,  # None if LLM failed
        "wheel_chart_url": wheel_chart_url,
        "created_at": created_at,
    }

    task_key = f"arq_task:{job_id}"
    task_payload = json.dumps({"status": "done", "result": result}, ensure_ascii=False)
    await redis.setex(task_key, ARQ_TASK_TTL, task_payload)
    logger.info("Worker: task_generate_natal_premium done | user_id=%s | job_id=%s", user_id, job_id)
    return result


async def task_generate_tarot_premium(
    ctx: dict[str, Any],
    *,
    user_id: int,
    question: str | None,
    spread_type: str,
    cards: list[dict[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    """Premium tarot via OpenRouter Gemini. Returns rich JSON report."""
    job_id: str = ctx["job_id"]
    redis = ctx["redis"]
    logger.info("Worker: task_generate_tarot_premium start | user_id=%s | job_id=%s", user_id, job_id)

    report = await interpret_tarot_premium_async(question=question, cards=cards)
    if report:
        logger.info("Worker: tarot premium LLM success | user_id=%s | job_id=%s", user_id, job_id)
    else:
        logger.error("Worker: tarot premium LLM failed | user_id=%s | job_id=%s", user_id, job_id)

    result = {
        "type": "tarot_premium",
        "question": question,
        "spread_type": spread_type,
        "cards": cards,
        "report": report,  # None if LLM failed
        "created_at": created_at,
    }
    task_key = f"arq_task:{job_id}"
    task_payload = json.dumps({"status": "done", "result": result}, ensure_ascii=False)
    await redis.setex(task_key, ARQ_TASK_TTL, task_payload)
    logger.info("Worker: task_generate_tarot_premium done | user_id=%s | job_id=%s", user_id, job_id)
    return result


async def on_worker_startup(ctx: dict[str, Any]) -> None:
    logger.info("ARQ worker started")


async def on_worker_shutdown(ctx: dict[str, Any]) -> None:
    logger.info("ARQ worker shutting down")


class WorkerSettings:
    functions = [task_generate_natal, task_generate_natal_premium, task_generate_stories, task_generate_numerology, task_generate_numerology_premium, task_generate_tarot_premium]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = on_worker_startup
    on_shutdown = on_worker_shutdown
    max_tries = 1  # LLM calls are expensive; don't retry automatically
    job_timeout = 120  # 2 minutes max per job
