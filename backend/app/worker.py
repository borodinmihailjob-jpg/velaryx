"""ARQ worker: async LLM tasks executed outside the HTTP request cycle."""
from __future__ import annotations

import json
import logging
from typing import Any

from arq.connections import RedisSettings

from .config import settings
from .database import SessionLocal
from .history import save_report_to_history
from . import star_payments as _star_payments
from .llm_engine import (
    interpret_natal_sections_async,
    interpret_natal_premium_async,
    interpret_forecast_stories_async,
    interpret_numerology_async,
    interpret_numerology_premium_async,
    interpret_tarot_premium_async,
    interpret_compat_free_async,
    interpret_compat_premium_async,
)

logger = logging.getLogger("astrobot.worker")

ARQ_TASK_TTL = 600  # 10 minutes — long enough for frontend polling

PREMIUM_LLM_FAILURE_MESSAGE = (
    "Премиум-функция временно недоступна: сбой при обращении к OpenRouter. "
    "Попробуйте еще раз через 1-2 минуты."
)


def _restore_premium_claim(job_id: str, user_id: int) -> None:
    """Restore a consumed payment/wallet debit so user can retry after LLM failure."""
    db = SessionLocal()
    try:
        restored = _star_payments.restore_premium_claim_by_task_id(db, job_id=job_id)
        if restored:
            logger.info("Worker: premium claim restored for retry | user_id=%s | job_id=%s", user_id, job_id)
        else:
            logger.warning("Worker: no claim found to restore | user_id=%s | job_id=%s", user_id, job_id)
    except Exception as exc:
        logger.error(
            "Worker: failed to restore premium claim | user_id=%s | job_id=%s | err=%s",
            user_id, job_id, exc,
        )
    finally:
        db.close()


async def task_generate_natal(
    ctx: dict[str, Any],
    *,
    user_id: int,
    tg_user_id: int,
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

    await save_report_to_history(
        redis=redis,
        tg_user_id=tg_user_id,
        report_type="natal_basic",
        report_id=chart_id,
        is_premium=False,
        summary={"sun_sign": sun_sign, "moon_sign": moon_sign, "rising_sign": rising_sign},
    )

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
    mbti_type: str | None = None,
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
        mbti_type=mbti_type,
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
    tg_user_id: int,
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

    try:
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
    except Exception as exc:
        logger.error("Worker: task_generate_numerology_premium exception | user_id=%s | job_id=%s | err=%s", user_id, job_id, exc)
        task_key = f"arq_task:{job_id}"
        task_payload = json.dumps({"status": "failed", "error": "Внутренняя ошибка при генерации отчёта"}, ensure_ascii=False)
        await redis.setex(task_key, ARQ_TASK_TTL, task_payload)
        _restore_premium_claim(job_id, user_id)
        raise

    if report:
        logger.info("Worker: numerology premium LLM success | user_id=%s | job_id=%s", user_id, job_id)
    else:
        logger.error("Worker: numerology premium LLM failed | user_id=%s | job_id=%s", user_id, job_id)
        task_key = f"arq_task:{job_id}"
        task_payload = json.dumps({"status": "failed", "error": PREMIUM_LLM_FAILURE_MESSAGE}, ensure_ascii=False)
        await redis.setex(task_key, ARQ_TASK_TTL, task_payload)
        _restore_premium_claim(job_id, user_id)
        return {"type": "numerology_premium", "numbers": {}, "report": None}

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

    report_preview = ""
    if isinstance(report, dict):
        for key in ("core_essence", "life_purpose", "strengths"):
            val = report.get(key)
            if isinstance(val, str) and val.strip():
                report_preview = val.strip()[:120]
                break
    await save_report_to_history(
        redis=redis,
        tg_user_id=tg_user_id,
        report_type="numerology_premium",
        report_id=f"{tg_user_id}_{birth_date}",
        is_premium=True,
        summary={
            "numbers": {
                "life_path": life_path,
                "expression": expression,
                "soul_urge": soul_urge,
                "personality": personality,
                "birthday": birthday,
            },
            "report_preview": report_preview,
        },
    )

    logger.info("Worker: task_generate_numerology_premium done | user_id=%s | job_id=%s", user_id, job_id)
    return result


async def task_generate_natal_premium(
    ctx: dict[str, Any],
    *,
    user_id: int,
    tg_user_id: int,
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
        task_key = f"arq_task:{job_id}"
        task_payload = json.dumps({"status": "failed", "error": PREMIUM_LLM_FAILURE_MESSAGE}, ensure_ascii=False)
        await redis.setex(task_key, ARQ_TASK_TTL, task_payload)
        _restore_premium_claim(job_id, user_id)
        return {
            "type": "natal_premium",
            "sun_sign": sun_sign,
            "moon_sign": moon_sign,
            "rising_sign": rising_sign,
            "report": None,
            "wheel_chart_url": wheel_chart_url,
            "created_at": created_at,
        }

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

    report_preview = ""
    if isinstance(report, dict):
        for key in ("core_essence", "life_mission", "strengths"):
            val = report.get(key)
            if isinstance(val, str) and val.strip():
                report_preview = val.strip()[:120]
                break
    await save_report_to_history(
        redis=redis,
        tg_user_id=tg_user_id,
        report_type="natal_premium",
        report_id=chart_id,
        is_premium=True,
        summary={
            "sun_sign": sun_sign,
            "moon_sign": moon_sign,
            "rising_sign": rising_sign,
            "report_preview": report_preview,
        },
    )

    logger.info("Worker: task_generate_natal_premium done | user_id=%s | job_id=%s", user_id, job_id)
    return result


async def task_generate_tarot_premium(
    ctx: dict[str, Any],
    *,
    user_id: int,
    tg_user_id: int,
    session_id: str,
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
        task_key = f"arq_task:{job_id}"
        task_payload = json.dumps({"status": "failed", "error": PREMIUM_LLM_FAILURE_MESSAGE}, ensure_ascii=False)
        await redis.setex(task_key, ARQ_TASK_TTL, task_payload)
        _restore_premium_claim(job_id, user_id)
        return {
            "type": "tarot_premium",
            "question": question,
            "spread_type": spread_type,
            "cards": cards,
            "report": None,
            "created_at": created_at,
        }

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

    report_preview = ""
    if isinstance(report, dict):
        for key in ("synthesis", "overall_energy", "advice"):
            val = report.get(key)
            if isinstance(val, str) and val.strip():
                report_preview = val.strip()[:120]
                break
    cards_summary = [
        {"card_name": c.get("card_name", ""), "is_reversed": c.get("is_reversed", False), "slot_label": c.get("slot_label", "")}
        for c in (cards or [])
    ]
    await save_report_to_history(
        redis=redis,
        tg_user_id=tg_user_id,
        report_type="tarot_premium",
        report_id=session_id,
        is_premium=True,
        summary={
            "spread_type": spread_type,
            "question": question,
            "cards": cards_summary,
            "report_preview": report_preview,
        },
    )

    logger.info("Worker: task_generate_tarot_premium done | user_id=%s | job_id=%s", user_id, job_id)
    return result


_COMPAT_FREE_FALLBACK_RESULT = {
    "compatibility_score": 60,
    "summary": "Оба знака дополняют друг друга в ключевых жизненных сферах. Энергетический потенциал союза выше среднего.",
    "strength": "Взаимное уважение и готовность к диалогу создают прочный фундамент.",
    "risk": "Возможны разногласия в темпах и приоритетах. Важна открытая коммуникация.",
    "advice": "Сфокусируйтесь на общих целях и регулярно сверяйте ожидания.",
}


async def task_generate_compat_free(
    ctx: dict[str, Any],
    *,
    user_id: int,
    tg_user_id: int,
    compat_type: str,
    sign_1: str,
    sign_2: str,
    name_1: str | None,
    name_2: str | None,
) -> dict[str, Any]:
    """Free compatibility report. Returns CompatFreeResult dict."""
    job_id: str = ctx["job_id"]
    redis = ctx["redis"]

    logger.info("Worker: task_generate_compat_free start | user_id=%s | job_id=%s", user_id, job_id)

    llm_result = await interpret_compat_free_async(
        compat_type=compat_type,
        sign_1=sign_1,
        sign_2=sign_2,
        name_1=name_1,
        name_2=name_2,
    )

    if llm_result:
        logger.info("Worker: compat free LLM success | user_id=%s | job_id=%s", user_id, job_id)
        compat_result = llm_result
    else:
        logger.warning("Worker: compat free LLM failed, using fallback | user_id=%s | job_id=%s", user_id, job_id)
        compat_result = _COMPAT_FREE_FALLBACK_RESULT

    result = {
        "type": "compat_free",
        "compat_type": compat_type,
        "person_1": {"sign": sign_1, "name": name_1},
        "person_2": {"sign": sign_2, "name": name_2},
        "result": compat_result,
        "status": "done",
    }

    task_key = f"arq_task:{job_id}"
    task_payload = json.dumps({"status": "done", "result": result}, ensure_ascii=False)
    await redis.setex(task_key, ARQ_TASK_TTL, task_payload)

    await save_report_to_history(
        redis=redis,
        tg_user_id=tg_user_id,
        report_type="compat_free",
        report_id=f"{tg_user_id}_{sign_1}_{sign_2}",
        is_premium=False,
        summary={"compat_type": compat_type, "sign_1": sign_1, "sign_2": sign_2, "score": compat_result.get("compatibility_score")},
    )

    logger.info("Worker: task_generate_compat_free done | user_id=%s | job_id=%s", user_id, job_id)
    return result


async def task_generate_compat_premium(
    ctx: dict[str, Any],
    *,
    user_id: int,
    tg_user_id: int,
    compat_type: str,
    sign_1: str,
    sign_2: str,
    name_1: str | None,
    name_2: str | None,
) -> dict[str, Any]:
    """Premium compatibility report via OpenRouter Gemini. Returns CompatPremiumResponse dict."""
    job_id: str = ctx["job_id"]
    redis = ctx["redis"]

    logger.info("Worker: task_generate_compat_premium start | user_id=%s | job_id=%s", user_id, job_id)

    try:
        report = await interpret_compat_premium_async(
            compat_type=compat_type,
            sign_1=sign_1,
            sign_2=sign_2,
            name_1=name_1,
            name_2=name_2,
        )
    except Exception as exc:
        logger.error("Worker: task_generate_compat_premium exception | user_id=%s | job_id=%s | err=%s", user_id, job_id, exc)
        task_key = f"arq_task:{job_id}"
        task_payload = json.dumps({"status": "failed", "error": "Внутренняя ошибка при генерации отчёта"}, ensure_ascii=False)
        await redis.setex(task_key, ARQ_TASK_TTL, task_payload)
        _restore_premium_claim(job_id, user_id)
        raise

    if not report:
        logger.error("Worker: compat premium LLM failed | user_id=%s | job_id=%s", user_id, job_id)
        task_key = f"arq_task:{job_id}"
        task_payload = json.dumps({"status": "failed", "error": PREMIUM_LLM_FAILURE_MESSAGE}, ensure_ascii=False)
        await redis.setex(task_key, ARQ_TASK_TTL, task_payload)
        _restore_premium_claim(job_id, user_id)
        return {"type": "compat_premium", "report": None}

    result = {
        "type": "compat_premium",
        "compat_type": compat_type,
        "person_1": {"sign": sign_1, "name": name_1},
        "person_2": {"sign": sign_2, "name": name_2},
        **report,
        "status": "done",
    }

    task_key = f"arq_task:{job_id}"
    task_payload = json.dumps({"status": "done", "result": result}, ensure_ascii=False)
    await redis.setex(task_key, ARQ_TASK_TTL, task_payload)

    await save_report_to_history(
        redis=redis,
        tg_user_id=tg_user_id,
        report_type="compat_premium",
        report_id=f"{tg_user_id}_{sign_1}_{sign_2}_premium",
        is_premium=True,
        summary={
            "compat_type": compat_type,
            "sign_1": sign_1,
            "sign_2": sign_2,
            "score": report.get("compatibility_score"),
            "report_preview": str(report.get("summary") or "")[:120],
        },
    )

    logger.info("Worker: task_generate_compat_premium done | user_id=%s | job_id=%s", user_id, job_id)
    return result


async def on_worker_startup(ctx: dict[str, Any]) -> None:
    logger.info("ARQ worker started")


async def on_worker_shutdown(ctx: dict[str, Any]) -> None:
    logger.info("ARQ worker shutting down")


class WorkerSettings:
    functions = [task_generate_natal, task_generate_natal_premium, task_generate_stories, task_generate_numerology, task_generate_numerology_premium, task_generate_tarot_premium, task_generate_compat_free, task_generate_compat_premium]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = on_worker_startup
    on_shutdown = on_worker_shutdown
    max_tries = 1  # LLM calls are expensive; don't retry automatically
    job_timeout = 300
