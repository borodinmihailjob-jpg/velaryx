from datetime import date, datetime, timezone
import hashlib
import json
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
import redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from . import models
from .config import settings
from .astro_engine import calculate_natal_chart
from .llm_engine import (
    interpret_combo_insight,
    interpret_forecast_stories,
    interpret_natal_sections,
    interpret_tarot_reading,
    llm_provider_label,
)
from .security import expiry_after_days, generate_token
from .tarot_engine import build_seed, card_image_url, draw_cards, supported_spreads

PLANET_LABELS_RU = {
    "sun": "Солнце",
    "moon": "Луна",
    "mercury": "Меркурий",
    "venus": "Венера",
    "mars": "Марс",
    "jupiter": "Юпитер",
    "saturn": "Сатурн",
    "uranus": "Уран",
    "neptune": "Нептун",
    "pluto": "Плутон",
}

ASPECT_LABELS_RU = {
    "conjunction": "соединение",
    "sextile": "секстиль",
    "square": "квадрат",
    "trine": "тригон",
    "opposition": "оппозиция",
}

SIGN_RU_EN = {
    "Овен": "Aries",
    "Телец": "Taurus",
    "Близнецы": "Gemini",
    "Рак": "Cancer",
    "Лев": "Leo",
    "Дева": "Virgo",
    "Весы": "Libra",
    "Скорпион": "Scorpio",
    "Стрелец": "Sagittarius",
    "Козерог": "Capricorn",
    "Водолей": "Aquarius",
    "Рыбы": "Pisces",
}


TAROT_HIDDEN_MESSAGE = "Карты скрыли ответ.\nВозможно, время ещё не пришло."
NATAL_LLM_CACHE_PREFIX = "natal:llm:v2"
NATAL_LLM_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
STORY_DEFAULT_TIMING = "10:30-13:00 и 16:30-19:00"

logger = logging.getLogger("astrobot.natal.llm_cache")
_redis_client: redis.Redis | None = None


def get_or_create_user(db: Session, tg_user_id: int) -> models.User:
    user = db.query(models.User).filter(models.User.tg_user_id == tg_user_id).first()
    if user:
        return user

    user = models.User(tg_user_id=tg_user_id)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        existing = db.query(models.User).filter(models.User.tg_user_id == tg_user_id).first()
        if existing:
            return existing
        raise


def _get_redis_client() -> redis.Redis | None:
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        _redis_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1.5,
            socket_timeout=1.5,
        )
        _redis_client.ping()
        return _redis_client
    except Exception as exc:
        logger.warning("Redis unavailable for natal LLM cache: %s", str(exc))
        _redis_client = None
        return None


def _normalize_llm_sections(payload: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in (
        "key_aspects",
        "planetary_profile",
        "house_cusps",
        "mc_axis",
        "lunar_nodes",
        "house_rulers",
        "dispositors",
        "essential_dignities",
        "configurations",
        "natal_explanation",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()
    return result


def create_birth_profile(
    db: Session,
    user_id: int,
    birth_date,
    birth_time,
    birth_place: str,
    latitude: float,
    longitude: float,
    timezone_name: str,
) -> models.BirthProfile:
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise HTTPException(status_code=422, detail="Invalid timezone")

    profile = models.BirthProfile(
        user_id=user_id,
        birth_date=birth_date,
        birth_time=birth_time,
        birth_place=birth_place,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone_name,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_latest_birth_profile(db: Session, user_id: int) -> models.BirthProfile:
    profile = (
        db.query(models.BirthProfile)
        .filter(models.BirthProfile.user_id == user_id)
        .order_by(models.BirthProfile.created_at.desc())
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Birth profile not found")
    return profile


def calculate_and_store_natal_chart(db: Session, user_id: int, profile_id) -> models.NatalChart:
    profile = (
        db.query(models.BirthProfile)
        .filter(models.BirthProfile.id == profile_id, models.BirthProfile.user_id == user_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Birth profile not found")

    payload = calculate_natal_chart(profile)
    sun_sign = payload["planets"]["sun"]["sign"]
    moon_sign = payload["planets"]["moon"]["sign"]
    rising_sign = payload["rising_sign"]

    chart = models.NatalChart(
        profile_id=profile.id,
        sun_sign=sun_sign,
        moon_sign=moon_sign,
        rising_sign=rising_sign,
        chart_payload=payload,
    )
    db.add(chart)
    db.commit()
    db.refresh(chart)
    return chart


def get_latest_natal_chart(db: Session, user_id: int) -> models.NatalChart:
    chart = (
        db.query(models.NatalChart)
        .join(models.BirthProfile, models.BirthProfile.id == models.NatalChart.profile_id)
        .filter(models.BirthProfile.user_id == user_id)
        .order_by(models.NatalChart.created_at.desc())
        .first()
    )
    if not chart:
        raise HTTPException(status_code=404, detail="Natal chart not found")
    return chart


def _format_natal_aspect(item: dict) -> str | None:
    if not isinstance(item, dict):
        return None
    p1 = PLANET_LABELS_RU.get(str(item.get("planet_1", "")).lower(), str(item.get("planet_1", "")))
    p2 = PLANET_LABELS_RU.get(str(item.get("planet_2", "")).lower(), str(item.get("planet_2", "")))
    asp = ASPECT_LABELS_RU.get(str(item.get("aspect", "")).lower(), str(item.get("aspect", "")))
    if not p1 or not p2 or not asp:
        return None
    orb = item.get("orb")
    if orb is None:
        return f"{p1} - {p2}: {asp}"
    try:
        return f"{p1} - {p2}: {asp} (орб {round(float(orb), 2)})"
    except (TypeError, ValueError):
        return f"{p1} - {p2}: {asp}"


def _extract_natal_material(
    *,
    chart_payload: dict,
    sun_sign: str,
    moon_sign: str,
    rising_sign: str,
) -> dict[str, list[str] | str]:
    interpretation = chart_payload.get("interpretation") if isinstance(chart_payload, dict) else {}
    if not isinstance(interpretation, dict):
        interpretation = {}

    full_aspect_lines: list[str] = []
    aspects = chart_payload.get("aspects") if isinstance(chart_payload, dict) else None
    if isinstance(aspects, list):
        for item in aspects[:24]:
            formatted = _format_natal_aspect(item)
            if formatted:
                full_aspect_lines.append(formatted)

    key_aspects_lines: list[str] = []
    raw_key_aspects = interpretation.get("key_aspects")
    if isinstance(raw_key_aspects, list):
        for item in raw_key_aspects[:8]:
            text = str(item).strip()
            if text:
                key_aspects_lines.append(text)
    if not key_aspects_lines and full_aspect_lines:
        key_aspects_lines = full_aspect_lines[:5]

    planets = chart_payload.get("planets") if isinstance(chart_payload, dict) else {}
    planetary_profile_lines: list[str] = []
    if isinstance(planets, dict) and planets:
        planet_order = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"]
        for key in planet_order:
            pdata = planets.get(key)
            if not isinstance(pdata, dict):
                continue
            sign = str(pdata.get("sign") or "—")
            lon = pdata.get("longitude")
            retro = bool(pdata.get("retrograde"))
            retro_suffix = ", ретроградно" if retro else ""
            label = PLANET_LABELS_RU.get(key, key.capitalize())
            if lon is None:
                planetary_profile_lines.append(f"{label}: {sign}{retro_suffix}")
            else:
                try:
                    planetary_profile_lines.append(f"{label}: {sign}, {round(float(lon), 2)}°{retro_suffix}")
                except (TypeError, ValueError):
                    planetary_profile_lines.append(f"{label}: {sign}{retro_suffix}")

    house_cusp_lines: list[str] = []
    houses = chart_payload.get("houses") if isinstance(chart_payload, dict) else None
    if isinstance(houses, list):
        for idx, deg in enumerate(houses[:12], start=1):
            try:
                house_cusp_lines.append(f"{idx} дом: {round(float(deg), 2)}°")
            except (TypeError, ValueError):
                continue

    planets_in_houses_lines: list[str] = []
    planets_in_houses = chart_payload.get("planets_in_houses") if isinstance(chart_payload, dict) else None
    if isinstance(planets_in_houses, dict):
        planet_order = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"]
        for key in planet_order:
            house_num = planets_in_houses.get(key)
            if house_num is None:
                continue
            label = PLANET_LABELS_RU.get(key, key.capitalize())
            planets_in_houses_lines.append(f"{label}: {house_num} дом")

    mc_line = ""
    mc = chart_payload.get("mc") if isinstance(chart_payload, dict) else None
    if isinstance(mc, dict):
        mc_sign = str(mc.get("sign") or "").strip()
        mc_lon = mc.get("longitude")
        if mc_sign:
            if mc_lon is None:
                mc_line = f"MC: {mc_sign}"
            else:
                try:
                    mc_line = f"MC: {mc_sign}, {round(float(mc_lon), 2)}°"
                except (TypeError, ValueError):
                    mc_line = f"MC: {mc_sign}"

    nodes_line = ""
    nodes = chart_payload.get("nodes") if isinstance(chart_payload, dict) else None
    if isinstance(nodes, dict):
        north = nodes.get("north")
        south = nodes.get("south")
        if isinstance(north, dict) and isinstance(south, dict):
            nsign = str(north.get("sign") or "").strip()
            ssign = str(south.get("sign") or "").strip()
            if nsign and ssign:
                nodes_line = f"Северный узел: {nsign} | Южный узел: {ssign}"

    house_rulers_lines: list[str] = []
    house_rulers = chart_payload.get("house_rulers") if isinstance(chart_payload, dict) else None
    if isinstance(house_rulers, list):
        for item in house_rulers[:12]:
            if not isinstance(item, dict):
                continue
            house_num = item.get("house")
            cusp_sign = str(item.get("cusp_sign") or "").strip()
            rulers = item.get("rulers")
            if house_num is None or not cusp_sign or not isinstance(rulers, list) or not rulers:
                continue

            ruler_parts: list[str] = []
            for ruler in rulers:
                if not isinstance(ruler, dict):
                    continue
                planet_ru = str(ruler.get("planet_ru") or "").strip()
                in_house = ruler.get("in_house")
                in_sign = str(ruler.get("in_sign") or "").strip()
                if not planet_ru:
                    continue
                if in_house is None:
                    ruler_parts.append(f"{planet_ru} в {in_sign}")
                else:
                    ruler_parts.append(f"{planet_ru} в {in_house} доме ({in_sign})")
            if ruler_parts:
                house_rulers_lines.append(f"{house_num} дом ({cusp_sign}): " + ", ".join(ruler_parts))

    dispositors_lines: list[str] = []
    dispositors = chart_payload.get("dispositors") if isinstance(chart_payload, dict) else None
    if isinstance(dispositors, list):
        for item in dispositors[:10]:
            if not isinstance(item, dict):
                continue
            planet_ru = str(item.get("planet_ru") or "").strip()
            primary = str(item.get("primary_dispositor_ru") or "").strip()
            final = str(item.get("final_dispositor_ru") or "").strip()
            is_cycle = bool(item.get("is_cycle"))
            if not planet_ru:
                continue
            if is_cycle:
                dispositors_lines.append(f"{planet_ru}: цепочка диспозиторов замкнута")
            elif primary and final:
                dispositors_lines.append(f"{planet_ru}: {primary} → финальный диспозитор {final}")
            elif primary:
                dispositors_lines.append(f"{planet_ru}: диспозитор {primary}")

    dignity_lines: list[str] = []
    essential_dignities = chart_payload.get("essential_dignities") if isinstance(chart_payload, dict) else None
    if isinstance(essential_dignities, dict):
        planets_dignities = essential_dignities.get("planets")
        if isinstance(planets_dignities, list):
            for item in planets_dignities[:10]:
                if not isinstance(item, dict):
                    continue
                planet_ru = str(item.get("planet_ru") or "").strip()
                score = item.get("score")
                tags_ru = item.get("tags_ru")
                if not planet_ru:
                    continue
                if isinstance(tags_ru, list) and tags_ru:
                    tags_text = ", ".join(str(tag) for tag in tags_ru if str(tag).strip())
                else:
                    tags_text = "нейтрально"
                dignity_lines.append(f"{planet_ru}: {tags_text} (балл {score})")
        total_score = essential_dignities.get("total_score")
        if total_score is not None:
            dignity_lines.append(f"Суммарный индекс силы карты: {total_score}")

    configurations_lines: list[str] = []
    configurations = chart_payload.get("configurations") if isinstance(chart_payload, dict) else None
    if isinstance(configurations, list):
        for item in configurations[:8]:
            if not isinstance(item, dict):
                continue
            ctype = str(item.get("type") or "").strip()
            ctype_ru = str(item.get("type_ru") or ctype).strip()
            members_ru = item.get("members_ru")
            if isinstance(members_ru, list) and members_ru:
                members_text = ", ".join(str(member) for member in members_ru if str(member).strip())
            else:
                members_text = ""
            if ctype == "stellium_sign":
                sign = str(item.get("sign") or "").strip()
                configurations_lines.append(f"{ctype_ru} ({sign}): {members_text}")
            elif ctype == "stellium_house":
                house = item.get("house")
                configurations_lines.append(f"{ctype_ru} ({house} дом): {members_text}")
            elif ctype == "t_square":
                apex_ru = str(item.get("apex_ru") or "").strip()
                configurations_lines.append(f"{ctype_ru}: вершина {apex_ru}; участники {members_text}")
            else:
                configurations_lines.append(f"{ctype_ru}: {members_text}")

    natal_summary = str(interpretation.get("summary") or "").strip() or (
        f"Солнце в {sun_sign}, Луна в {moon_sign}, Асцендент в {rising_sign}."
    )
    return {
        "key_aspects_lines": key_aspects_lines,
        "planetary_profile_lines": planetary_profile_lines,
        "house_cusp_lines": house_cusp_lines,
        "planets_in_houses_lines": planets_in_houses_lines,
        "mc_line": mc_line,
        "nodes_line": nodes_line,
        "house_rulers_lines": house_rulers_lines,
        "dispositors_lines": dispositors_lines,
        "dignity_lines": dignity_lines,
        "configurations_lines": configurations_lines,
        "full_aspect_lines": full_aspect_lines,
        "natal_summary": natal_summary,
    }


def _natal_llm_cache_fingerprint(
    *,
    material: dict[str, list[str] | str],
    sun_sign: str,
    moon_sign: str,
    rising_sign: str,
) -> str:
    payload = {
        "sun_sign": sun_sign,
        "moon_sign": moon_sign,
        "rising_sign": rising_sign,
        "natal_summary": str(material.get("natal_summary") or ""),
        "key_aspects": list(material.get("key_aspects_lines") or []),
        "planetary_profile": list(material.get("planetary_profile_lines") or []),
        "house_cusps": list(material.get("house_cusp_lines") or []),
        "planets_in_houses": list(material.get("planets_in_houses_lines") or []),
        "mc_line": str(material.get("mc_line") or ""),
        "nodes_line": str(material.get("nodes_line") or ""),
        "house_rulers": list(material.get("house_rulers_lines") or []),
        "dispositors": list(material.get("dispositors_lines") or []),
        "essential_dignities": list(material.get("dignity_lines") or []),
        "configurations": list(material.get("configurations_lines") or []),
        "full_aspects": list(material.get("full_aspect_lines") or []),
        "provider": settings.llm_provider,
        "model": llm_provider_label() or "unknown",
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _natal_llm_cache_key(user_id: int, fingerprint: str) -> str:
    return f"{NATAL_LLM_CACHE_PREFIX}:{user_id}:{fingerprint}"


def _get_cached_natal_llm_sections(user_id: int, fingerprint: str) -> dict[str, str] | None:
    client = _get_redis_client()
    if client is None:
        return None

    key = _natal_llm_cache_key(user_id, fingerprint)
    try:
        raw = client.get(key)
    except Exception as exc:
        logger.warning("Redis read failed for natal LLM cache key=%s: %s", key, str(exc))
        return None
    if not raw:
        logger.info("Natal LLM cache miss | user_id=%s | fingerprint=%s", user_id, fingerprint[:12])
        return None

    try:
        payload = json.loads(raw)
    except Exception as exc:
        logger.warning("Invalid natal LLM cache payload key=%s: %s", key, str(exc))
        return None
    if not isinstance(payload, dict):
        return None

    normalized = _normalize_llm_sections(payload)
    if not normalized:
        return None

    logger.info("Natal LLM cache hit | user_id=%s | fingerprint=%s", user_id, fingerprint[:12])
    return normalized


def _set_cached_natal_llm_sections(user_id: int, fingerprint: str, llm_sections: dict[str, str]) -> None:
    client = _get_redis_client()
    if client is None:
        return

    normalized = _normalize_llm_sections(llm_sections)
    if not normalized:
        return

    key = _natal_llm_cache_key(user_id, fingerprint)
    try:
        client.setex(
            key,
            NATAL_LLM_CACHE_TTL_SECONDS,
            json.dumps(normalized, ensure_ascii=False, separators=(",", ":")),
        )
        logger.info("Natal LLM cache store | user_id=%s | fingerprint=%s", user_id, fingerprint[:12])
    except Exception as exc:
        logger.warning("Redis write failed for natal LLM cache key=%s: %s", key, str(exc))


def _build_natal_sections(
    *,
    material: dict[str, list[str] | str],
    llm_sections: dict[str, str] | None = None,
) -> list[dict]:
    llm_sections = llm_sections or {}
    key_aspects_lines = list(material.get("key_aspects_lines") or [])
    planetary_profile_lines = list(material.get("planetary_profile_lines") or [])
    house_cusp_lines = list(material.get("house_cusp_lines") or [])
    planets_in_houses_lines = list(material.get("planets_in_houses_lines") or [])
    mc_line = str(material.get("mc_line") or "")
    nodes_line = str(material.get("nodes_line") or "")
    house_rulers_lines = list(material.get("house_rulers_lines") or [])
    dispositors_lines = list(material.get("dispositors_lines") or [])
    dignity_lines = list(material.get("dignity_lines") or [])
    configurations_lines = list(material.get("configurations_lines") or [])
    natal_summary = str(material.get("natal_summary") or "")

    if key_aspects_lines:
        key_aspects_fallback = (
            "Ключевые связки карты: "
            f"{' • '.join(key_aspects_lines[:4])}. "
            "Практика: усиливайте решения через последовательность и фиксируйте результат письменно."
        )
    else:
        key_aspects_fallback = (
            "Ключевые аспекты не выделены автоматически. "
            "Ориентир на день: один приоритет, один измеримый шаг, минимум переключений."
        )

    if planetary_profile_lines:
        planetary_profile_fallback = (
            "Планетный профиль: "
            f"{' | '.join(planetary_profile_lines[:6])}. "
            "Что усилить: регулярный ритм действий. Чего избегать: спонтанных решений на эмоциях."
        )
    else:
        planetary_profile_fallback = (
            "Планетный профиль временно недоступен. "
            "Используйте базовый режим: сначала план, затем действие, затем короткая проверка результата."
        )

    if house_cusp_lines:
        house_cusps_fallback = (
            "Куспиды домов: "
            f"{' • '.join(house_cusp_lines[:6])}. "
            "Практика: распределяйте энергию по сферам жизни, не перегружая один сектор."
        )
    else:
        house_cusps_fallback = (
            "Куспиды домов временно недоступны. "
            "Рекомендация: держите баланс между работой, отношениями и восстановлением ресурса."
        )

    if mc_line:
        mc_axis_fallback = (
            f"{mc_line}. "
            "Практика: карьерные решения сверяйте с долгосрочной целью, а не только с быстрым результатом."
        )
    else:
        mc_axis_fallback = (
            "MC пока не определён в расчёте. "
            "Рекомендация: опишите профессиональную цель на 3-6 месяцев и привяжите к ней текущие действия."
        )

    if nodes_line:
        lunar_nodes_fallback = (
            f"{nodes_line}. "
            "Ориентир: меньше повторять старые сценарии и больше выбирать новые, но посильные шаги роста."
        )
    else:
        lunar_nodes_fallback = (
            "Лунные узлы пока не определены. "
            "Практика: отслеживайте повторяющиеся паттерны и заменяйте их конкретной новой стратегией."
        )

    if house_rulers_lines:
        house_rulers_fallback = (
            "Управители домов: "
            f"{' • '.join(house_rulers_lines[:6])}. "
            "Используйте эти связи, чтобы понимать, как одно решение влияет на соседние сферы жизни."
        )
    else:
        house_rulers_fallback = (
            "Управители домов пока не рассчитаны. "
            "Рекомендация: оценивайте каждую цель через влияние на работу, отношения и ресурс."
        )

    if dispositors_lines:
        dispositors_fallback = (
            "Цепочки диспозиторов: "
            f"{' • '.join(dispositors_lines[:6])}. "
            "Практика: отслеживайте финальный диспозитор как опорный стиль принятия решений."
        )
    else:
        dispositors_fallback = (
            "Диспозиторы пока не рассчитаны. "
            "Практика: ищите, какие планеты повторяются как связующие между ключевыми темами карты."
        )

    if dignity_lines:
        essential_dignities_fallback = (
            "Эссенциальные достоинства: "
            f"{' • '.join(dignity_lines[:6])}. "
            "Чем выше балл планеты, тем проще проявлять ее качества экологично и стабильно."
        )
    else:
        essential_dignities_fallback = (
            "Эссенциальные достоинства пока не определены. "
            "Практика: опирайтесь на те качества, которые проявляются без внутреннего сопротивления."
        )

    if configurations_lines:
        configurations_fallback = (
            "Конфигурации карты: "
            f"{' • '.join(configurations_lines[:6])}. "
            "Эти фигуры показывают зоны концентрации, напряжения и естественных точек роста."
        )
    else:
        configurations_fallback = (
            "Явные конфигурации (T-квадрат, стеллиум, большой тригон) не выделены. "
            "Практика: опирайтесь на аспекты с минимальным орбом как на главный приоритет анализа."
        )

    natal_explanation_fallback = (
        natal_summary
        if natal_summary
        else "Натальная карта сформирована. Главный ориентир: опирайтесь на сильные качества, "
        "выбирайте конкретные цели и корректируйте курс по фактическому результату."
    )

    return [
        {
            "title": "Ключевые аспекты",
            "text": str(llm_sections.get("key_aspects") or key_aspects_fallback),
            "icon": "🔭",
        },
        {
            "title": "Планетный профиль",
            "text": str(llm_sections.get("planetary_profile") or planetary_profile_fallback),
            "icon": "🪐",
        },
        {
            "title": "Куспиды домов",
            "text": str(llm_sections.get("house_cusps") or house_cusps_fallback),
            "icon": "🏛️",
        },
        {
            "title": "Планеты в домах",
            "text": (
                "Позиции планет по домам: "
                f"{' • '.join(planets_in_houses_lines[:8])}. "
                "Практика: сферы с плотным скоплением планет требуют больше внимания и дисциплины."
                if planets_in_houses_lines
                else "Позиции планет по домам пока недоступны."
            ),
            "icon": "🧭",
        },
        {
            "title": "MC и социальная реализация",
            "text": str(llm_sections.get("mc_axis") or mc_axis_fallback),
            "icon": "🏔️",
        },
        {
            "title": "Лунные узлы",
            "text": str(llm_sections.get("lunar_nodes") or lunar_nodes_fallback),
            "icon": "☊",
        },
        {
            "title": "Управители домов",
            "text": str(llm_sections.get("house_rulers") or house_rulers_fallback),
            "icon": "🗝️",
        },
        {
            "title": "Диспозиторы",
            "text": str(llm_sections.get("dispositors") or dispositors_fallback),
            "icon": "🧬",
        },
        {
            "title": "Эссенциальные достоинства",
            "text": str(llm_sections.get("essential_dignities") or essential_dignities_fallback),
            "icon": "⚖️",
        },
        {
            "title": "Конфигурации карты",
            "text": str(llm_sections.get("configurations") or configurations_fallback),
            "icon": "🕸️",
        },
        {
            "title": "Объяснение твоей натальной карты",
            "text": str(llm_sections.get("natal_explanation") or natal_explanation_fallback),
            "icon": "🔮",
        },
    ]


def _natal_sections_from_payload(chart: models.NatalChart, user_id: int) -> list[dict]:
    chart_payload = chart.chart_payload if isinstance(chart.chart_payload, dict) else {}

    material = _extract_natal_material(
        chart_payload=chart_payload,
        sun_sign=str(chart.sun_sign or ""),
        moon_sign=str(chart.moon_sign or ""),
        rising_sign=str(chart.rising_sign or ""),
    )
    fingerprint = _natal_llm_cache_fingerprint(
        material=material,
        sun_sign=str(chart.sun_sign or ""),
        moon_sign=str(chart.moon_sign or ""),
        rising_sign=str(chart.rising_sign or ""),
    )

    llm_sections = _get_cached_natal_llm_sections(user_id=user_id, fingerprint=fingerprint)
    if llm_sections is None:
        generated = interpret_natal_sections(
            sun_sign=str(chart.sun_sign or ""),
            moon_sign=str(chart.moon_sign or ""),
            rising_sign=str(chart.rising_sign or ""),
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
        llm_sections = _normalize_llm_sections(generated or {})
        if llm_sections:
            _set_cached_natal_llm_sections(user_id=user_id, fingerprint=fingerprint, llm_sections=llm_sections)

    return _build_natal_sections(material=material, llm_sections=llm_sections)


def get_full_natal_chart(db: Session, user_id: int) -> tuple[models.NatalChart, list[dict], str | None]:
    chart = get_latest_natal_chart(db=db, user_id=user_id)
    sections = _natal_sections_from_payload(chart=chart, user_id=user_id)
    wheel_chart_url = None
    payload = chart.chart_payload if isinstance(chart.chart_payload, dict) else {}
    candidate = payload.get("wheel_chart_url")
    if isinstance(candidate, str) and candidate.strip():
        wheel_chart_url = candidate.strip()
    return chart, sections, wheel_chart_url


def _build_daily_summary(sun_sign: str, moon_sign: str, rising_sign: str, day_seed: int) -> tuple[int, str, dict]:
    energy_score = 45 + (day_seed % 55)
    mood = ["баланс", "прорыв", "рефлексия", "инициатива", "забота"][day_seed % 5]
    focus = ["отношениях", "карьере", "финансах", "здоровье", "обучении"][day_seed % 5]

    summary = (
        f"Сегодня акцент на {focus}: энергия {energy_score}/100. "
        f"Солнечный знак {sun_sign}, Луна в {moon_sign}, Асцендент {rising_sign}. "
        f"Режим дня: {mood}."
    )
    payload = {
        "sun_sign": sun_sign,
        "moon_sign": moon_sign,
        "rising_sign": rising_sign,
        "mood": mood,
        "focus": focus,
    }
    return energy_score, summary, payload


def get_or_create_daily_forecast(db: Session, user_id: int, forecast_date: date) -> models.DailyForecast:
    existing = (
        db.query(models.DailyForecast)
        .filter(models.DailyForecast.user_id == user_id, models.DailyForecast.forecast_date == forecast_date)
        .first()
    )
    if existing:
        return existing

    chart = get_latest_natal_chart(db, user_id)
    day_seed = (forecast_date.toordinal() + user_id) % 1000
    energy_score, summary, payload = _build_daily_summary(
        sun_sign=chart.sun_sign,
        moon_sign=chart.moon_sign,
        rising_sign=chart.rising_sign,
        day_seed=day_seed,
    )

    forecast = models.DailyForecast(
        user_id=user_id,
        forecast_date=forecast_date,
        energy_score=energy_score,
        summary=summary,
        payload=payload,
    )
    db.add(forecast)
    db.commit()
    db.refresh(forecast)
    return forecast


def _story_focus_playbook(focus: str) -> dict[str, str]:
    normalized = focus.strip().lower()
    mapping = {
        "отношениях": {
            "work_tip": "Назначьте один разговор, который давно откладывали, и заранее сформулируйте цель.",
            "work_avoid": "Не обсуждайте важное в спешке и на эмоциях.",
            "work_timing": "11:00-13:00 для переговоров и сверки ожиданий.",
            "social_tip": "Спросите человека о его текущем запросе, прежде чем давать совет.",
            "social_avoid": "Не делайте выводы по тону сообщения без уточнения.",
            "social_timing": "18:00-21:00 для теплого диалога и встреч.",
            "self_tip": "15 минут тишины без экрана перед сном снизят внутренний шум.",
            "self_avoid": "Не перегружайте себя чужими задачами в ущерб своим.",
        },
        "карьере": {
            "work_tip": "Сделайте один сложный блок задач в первой половине дня без переключений.",
            "work_avoid": "Не распыляйтесь на многозадачность и мелкие срочные запросы.",
            "work_timing": "09:30-12:00 для приоритетной задачи и решений.",
            "social_tip": "На созвоне фиксируйте договоренности сразу в заметках.",
            "social_avoid": "Не соглашайтесь на новые дедлайны без оценки нагрузки.",
            "social_timing": "14:00-16:00 для встреч и согласований.",
            "self_tip": "После рабочего пика сделайте прогулку 20 минут для восстановления фокуса.",
            "self_avoid": "Не переносите рабочие мысли в вечер без плана на завтра.",
        },
        "финансах": {
            "work_tip": "Проверьте автосписания и уберите одну лишнюю статью расходов сегодня.",
            "work_avoid": "Не принимайте импульсивные решения о крупных покупках.",
            "work_timing": "12:00-15:00 для расчётов, бюджета и сравнения вариантов.",
            "social_tip": "Если обсуждаете деньги, проговорите сумму, срок и формат письменно.",
            "social_avoid": "Не одалживайте, если нет четких условий возврата.",
            "social_timing": "17:00-19:00 для спокойных финансовых договоренностей.",
            "self_tip": "Закройте день короткой ревизией: что дало пользу, а что было лишним.",
            "self_avoid": "Не компенсируйте стресс спонтанными тратами.",
        },
        "здоровье": {
            "work_tip": "Разбейте день на блоки 50/10: 50 минут фокус, 10 минут перерыв.",
            "work_avoid": "Не пропускайте воду и еду в активные часы.",
            "work_timing": "08:30-11:30 для продуктивной работы с ясной головой.",
            "social_tip": "Сократите лишние чаты, чтобы не перегружать нервную систему.",
            "social_avoid": "Не втягивайтесь в конфликты, когда чувствуете усталость.",
            "social_timing": "15:00-18:00 для спокойной коммуникации.",
            "self_tip": "Добавьте мягкую физическую нагрузку и ранний уход в сон.",
            "self_avoid": "Не дожимайте себя через силу в вечерние часы.",
        },
        "обучении": {
            "work_tip": "Выберите одну тему и сделайте 30 минут глубокой практики с конспектом.",
            "work_avoid": "Не перескакивайте между курсами и форматами.",
            "work_timing": "10:00-12:30 для нового материала и закрепления.",
            "social_tip": "Обсудите тему с человеком, который уже применял её на практике.",
            "social_avoid": "Не спорьте о теории, пока нет собственного теста.",
            "social_timing": "18:30-20:30 для обмена опытом и вопросов.",
            "self_tip": "Закройте день коротким повторением ключевых тезисов на 10 минут.",
            "self_avoid": "Не пытайтесь выучить всё за один день.",
        },
    }
    default = {
        "work_tip": "Выберите одну задачу с максимальным эффектом и завершите её до вечера.",
        "work_avoid": "Не разбрасывайтесь на второстепенные дела.",
        "work_timing": STORY_DEFAULT_TIMING,
        "social_tip": "Сначала слушайте, затем формулируйте свою позицию коротко и ясно.",
        "social_avoid": "Не отвечайте резко, если устали.",
        "social_timing": "17:30-20:00 для спокойного диалога.",
        "self_tip": "20 минут тишины или прогулки выровняют эмоциональный фон.",
        "self_avoid": "Не откладывайте отдых до полного выгорания.",
    }
    return mapping.get(normalized, default)


def _build_fallback_story_slides(chart: models.NatalChart, forecast: models.DailyForecast, interpretation: dict) -> list[dict]:
    payload = forecast.payload if isinstance(forecast.payload, dict) else {}
    mood = str(payload.get("mood") or "баланс")
    focus = str(payload.get("focus") or "приоритетах")
    playbook = _story_focus_playbook(focus)

    key_aspects = interpretation.get("key_aspects")
    first_aspect = ""
    if isinstance(key_aspects, list) and key_aspects:
        first_aspect = str(key_aspects[0]).strip()
    if not first_aspect:
        first_aspect = "Делайте ставку на последовательность и аккуратную коммуникацию."

    return [
        {
            "title": "Пульс дня",
            "body": (
                f"Энергия дня {forecast.energy_score}/100, режим: {mood}. "
                f"Связка Солнце {chart.sun_sign}, Луна {chart.moon_sign}, Асцендент {chart.rising_sign} "
                f"лучше раскрывается через фокус на {focus}."
            ),
            "badge": f"{forecast.energy_score}/100",
            "tip": f"Главный шаг: {playbook['work_tip']}",
            "avoid": playbook["work_avoid"],
            "timing": playbook["work_timing"],
            "animation": "glow",
        },
        {
            "title": "Работа и решения",
            "body": (
                "Сегодня выигрывает структура: один приоритет, один измеримый результат. "
                f"Ключ натала: {first_aspect}"
            ),
            "badge": f"Фокус: {focus}",
            "tip": playbook["work_tip"],
            "avoid": playbook["work_avoid"],
            "timing": playbook["work_timing"],
            "animation": "pulse",
        },
        {
            "title": "Люди и диалог",
            "body": (
                "В общении день просит ясных формулировок и спокойного темпа. "
                "Лучше проверять договорённости письменно."
            ),
            "badge": f"Режим: {mood}",
            "tip": playbook["social_tip"],
            "avoid": playbook["social_avoid"],
            "timing": playbook["social_timing"],
            "animation": "orbit",
        },
        {
            "title": "Ресурс и восстановление",
            "body": (
                "Ваш личный КПД сегодня выше, если чередовать нагрузку и короткие паузы. "
                "Вечером важнее восстановить нервную систему, чем добивать задачи."
            ),
            "badge": "Баланс",
            "tip": playbook["self_tip"],
            "avoid": playbook["self_avoid"],
            "timing": "После 20:00 — мягкий режим и снижение инфошума.",
            "animation": "float",
        },
    ]


def build_forecast_story_slides(chart: models.NatalChart, forecast: models.DailyForecast) -> tuple[list[dict], str | None]:
    interpretation = {}
    if isinstance(chart.chart_payload, dict):
        interpretation = chart.chart_payload.get("interpretation", {}) or {}

    key_aspects = interpretation.get("key_aspects")
    aspects_list: list[str] = []
    if isinstance(key_aspects, list):
        for item in key_aspects[:4]:
            text = str(item).strip()
            if text:
                aspects_list.append(text)

    payload = forecast.payload if isinstance(forecast.payload, dict) else {}
    mood = str(payload.get("mood") or "баланс")
    focus = str(payload.get("focus") or "приоритетах")
    natal_summary = str(interpretation.get("summary") or "").strip()

    llm_slides = interpret_forecast_stories(
        sun_sign=str(chart.sun_sign or ""),
        moon_sign=str(chart.moon_sign or ""),
        rising_sign=str(chart.rising_sign or ""),
        energy_score=int(forecast.energy_score or 0),
        mood=mood,
        focus=focus,
        natal_summary=natal_summary,
        key_aspects=aspects_list,
    )
    if llm_slides:
        return llm_slides, llm_provider_label()

    fallback_slides = _build_fallback_story_slides(chart=chart, forecast=forecast, interpretation=interpretation)
    return fallback_slides, "local:fallback"


def _sign_compatibility(inviter_sign: str, invitee_sign: str) -> tuple[int, list[str], list[str]]:
    inviter_sign = SIGN_RU_EN.get(inviter_sign, inviter_sign)
    invitee_sign = SIGN_RU_EN.get(invitee_sign, invitee_sign)

    if inviter_sign == invitee_sign:
        return (
            88,
            ["Похожий жизненный темп", "Легко понимать мотивацию друг друга"],
            ["Риск зациклиться в одном паттерне", "Нужны свежие впечатления извне"],
        )

    supportive_pairs = {
        ("Aries", "Leo"),
        ("Aries", "Sagittarius"),
        ("Taurus", "Virgo"),
        ("Taurus", "Capricorn"),
        ("Gemini", "Libra"),
        ("Gemini", "Aquarius"),
        ("Cancer", "Scorpio"),
        ("Cancer", "Pisces"),
        ("Leo", "Sagittarius"),
        ("Virgo", "Capricorn"),
        ("Libra", "Aquarius"),
        ("Scorpio", "Pisces"),
    }
    if (inviter_sign, invitee_sign) in supportive_pairs or (invitee_sign, inviter_sign) in supportive_pairs:
        return (
            81,
            ["Естественная взаимная поддержка", "Хорошая эмоциональная синхронизация"],
            ["Важно не замалчивать ожидания", "Сохранять личные границы"],
        )

    return (
        69,
        ["Притяжение через различия", "Потенциал личного роста в паре"],
        ["Потребуется ясная коммуникация", "Нужно договариваться о темпе и приоритетах"],
    )


def draw_tarot_reading(
    db: Session,
    user_id: int,
    spread_type: str,
    question: str | None,
) -> models.TarotSession:
    if spread_type not in supported_spreads():
        raise HTTPException(status_code=422, detail=f"Unsupported spread_type: {spread_type}")

    seed = build_seed(
        user_id=user_id,
        spread_type=spread_type,
        question=question,
        salt=datetime.now(timezone.utc).isoformat(),
    )
    cards_payload = draw_cards(spread_type=spread_type, seed=seed)

    session = models.TarotSession(
        user_id=user_id,
        spread_type=spread_type,
        question=question,
        seed=seed,
    )
    db.add(session)
    db.flush()

    for card in cards_payload:
        db.add(
            models.TarotCard(
                session_id=session.id,
                position=card["position"],
                slot_label=card["slot_label"],
                card_name=card["card_name"],
                is_reversed=card["is_reversed"],
                meaning=card["meaning"],
            )
        )

    db.commit()
    db.refresh(session)
    return session


def get_tarot_session(db: Session, user_id: int, session_id) -> models.TarotSession:
    session = (
        db.query(models.TarotSession)
        .options(joinedload(models.TarotSession.cards))
        .filter(models.TarotSession.id == session_id, models.TarotSession.user_id == user_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Tarot session not found")
    return session


def build_tarot_cards_payload(cards: list[models.TarotCard]) -> list[dict]:
    return [
        {
            "position": card.position,
            "slot_label": card.slot_label,
            "card_name": card.card_name,
            "is_reversed": card.is_reversed,
            "meaning": card.meaning,
            "image_url": card_image_url(card.card_name),
            "provider": settings.tarot_provider,
        }
        for card in sorted(cards, key=lambda c: c.position)
    ]


def build_tarot_ai_interpretation(question: str | None, cards_payload: list[dict]) -> tuple[str | None, str | None]:
    text = interpret_tarot_reading(question=question, cards=cards_payload)
    if text:
        return text, llm_provider_label()
    return TAROT_HIDDEN_MESSAGE, "local:fallback"


def build_combo_insight(
    db: Session,
    user_id: int,
    question: str | None,
    spread_type: str,
) -> tuple[models.NatalChart, models.DailyForecast, models.TarotSession, list[dict], str, str | None]:
    chart = get_latest_natal_chart(db=db, user_id=user_id)
    forecast = get_or_create_daily_forecast(db=db, user_id=user_id, forecast_date=date.today())

    session = draw_tarot_reading(
        db=db,
        user_id=user_id,
        spread_type=spread_type,
        question=question,
    )
    session_with_cards = get_tarot_session(db=db, user_id=user_id, session_id=session.id)
    tarot_cards_payload = build_tarot_cards_payload(session_with_cards.cards)

    first_card = tarot_cards_payload[0]["card_name"] if tarot_cards_payload else "карты"
    natal_summary = chart.chart_payload.get("interpretation", {}).get("summary", "")
    combined_advice = (
        f"{natal_summary} Сегодняшний фокус: {forecast.payload.get('focus', 'баланс')}. "
        f"Ключ карты дня: {first_card}. Действуйте через маленькие шаги и фиксируйте результат."
    ).strip()
    llm_provider = None

    llm_advice = interpret_combo_insight(
        question=question,
        natal_summary=str(natal_summary or ""),
        daily_summary=str(forecast.summary or ""),
        cards=tarot_cards_payload,
    )
    if llm_advice:
        combined_advice = llm_advice
        llm_provider = llm_provider_label()
    else:
        llm_provider = "local:fallback"

    return chart, forecast, session_with_cards, tarot_cards_payload, combined_advice, llm_provider


def create_compat_invite(db: Session, inviter_user_id: int, ttl_days: int, max_uses: int) -> models.CompatInvite:
    invite = models.CompatInvite(
        token=generate_token("comp_"),
        inviter_user_id=inviter_user_id,
        expires_at=expiry_after_days(ttl_days),
        used=False,
        max_uses=max_uses,
        use_count=0,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


def start_compat_session(db: Session, invite_token: str, invitee_user_id: int) -> tuple[models.CompatSession, models.CompatResult]:
    invite = db.query(models.CompatInvite).filter(models.CompatInvite.token == invite_token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    now = datetime.now(timezone.utc)
    invite_expires = invite.expires_at
    if invite_expires.tzinfo is None:
        invite_expires = invite_expires.replace(tzinfo=timezone.utc)

    if invite_expires < now:
        raise HTTPException(status_code=410, detail="Invite expired")

    if invite.use_count >= invite.max_uses:
        raise HTTPException(status_code=409, detail="Invite already exhausted")

    invite.use_count += 1
    invite.used = invite.use_count >= invite.max_uses

    session = models.CompatSession(
        inviter_user_id=invite.inviter_user_id,
        invitee_user_id=invitee_user_id,
        invite_token=invite.token,
    )
    db.add(session)
    db.flush()

    inviter_chart = (
        db.query(models.NatalChart)
        .join(models.BirthProfile, models.BirthProfile.id == models.NatalChart.profile_id)
        .filter(models.BirthProfile.user_id == invite.inviter_user_id)
        .order_by(models.NatalChart.created_at.desc())
        .first()
    )
    invitee_chart = (
        db.query(models.NatalChart)
        .join(models.BirthProfile, models.BirthProfile.id == models.NatalChart.profile_id)
        .filter(models.BirthProfile.user_id == invitee_user_id)
        .order_by(models.NatalChart.created_at.desc())
        .first()
    )

    if inviter_chart and invitee_chart:
        score, strengths, growth_areas = _sign_compatibility(inviter_chart.sun_sign, invitee_chart.sun_sign)
    else:
        seed = (invite.inviter_user_id + invitee_user_id + invite.use_count) % 100
        score = max(45, seed)
        strengths = ["Есть потенциал взаимного интереса", "Пара может быстро находить общую цель"]
        growth_areas = ["Важна регулярная обратная связь", "Нужны договоренности по ожиданиям"]

    detail_payload = {
        "chemistry": max(40, score - 5),
        "communication": min(99, score + 3),
        "stability": max(35, score - 8),
        "strengths": strengths,
        "growth_areas": growth_areas,
    }
    result = models.CompatResult(
        session_id=session.id,
        score=score,
        summary="Высокий потенциал, важен осознанный диалог и поддержка.",
        payload=detail_payload,
    )
    db.add(result)
    db.commit()
    db.refresh(session)
    db.refresh(result)
    return session, result


def create_wishlist(
    db: Session,
    owner_user_id: int,
    title: str,
    slug: str,
    is_public: bool,
    cover_url: str | None,
) -> models.Wishlist:
    wishlist = models.Wishlist(
        owner_user_id=owner_user_id,
        title=title,
        slug=slug,
        is_public=is_public,
        public_token=generate_token("wl_"),
        cover_url=cover_url,
    )
    db.add(wishlist)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug already exists")
    db.refresh(wishlist)
    return wishlist


def add_wishlist_item(
    db: Session,
    user_id: int,
    wishlist_id,
    title: str,
    image_url: str | None,
    budget_cents: int | None,
) -> models.WishlistItem:
    wishlist = db.query(models.Wishlist).filter(models.Wishlist.id == wishlist_id).first()
    if not wishlist:
        raise HTTPException(status_code=404, detail="Wishlist not found")
    if wishlist.owner_user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your wishlist")

    item = models.WishlistItem(
        wishlist_id=wishlist.id,
        title=title,
        image_url=image_url,
        budget_cents=budget_cents,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_public_wishlist(db: Session, public_token: str) -> models.Wishlist:
    wishlist = (
        db.query(models.Wishlist)
        .options(
            joinedload(models.Wishlist.items).joinedload(models.WishlistItem.reservations),
        )
        .filter(models.Wishlist.public_token == public_token, models.Wishlist.is_public.is_(True))
        .first()
    )
    if not wishlist:
        raise HTTPException(status_code=404, detail="Wishlist not found")
    return wishlist


def reserve_item(
    db: Session,
    public_token: str,
    item_id,
    reserver_tg_user_id: int | None,
    reserver_name: str | None,
) -> models.ItemReservation:
    wishlist = get_public_wishlist(db, public_token)
    item = (
        db.query(models.WishlistItem)
        .filter(models.WishlistItem.id == item_id, models.WishlistItem.wishlist_id == wishlist.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    existing = (
        db.query(models.ItemReservation)
        .filter(models.ItemReservation.item_id == item.id, models.ItemReservation.active.is_(True))
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Item already reserved")

    reservation = models.ItemReservation(
        item_id=item.id,
        reserver_tg_user_id=reserver_tg_user_id,
        reserver_name=reserver_name,
        active=True,
    )
    db.add(reservation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Item already reserved")
    db.refresh(reservation)
    return reservation
