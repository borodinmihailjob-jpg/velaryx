from datetime import datetime, timezone
from itertools import combinations
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from .config import settings
from .models import BirthProfile

try:
    import swisseph as swe
except Exception:  # pragma: no cover
    swe = None

SIGNS = (
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
)

PLANETS = {
    "sun": 0,
    "moon": 1,
    "mercury": 2,
    "venus": 3,
    "mars": 4,
    "jupiter": 5,
    "saturn": 6,
    "uranus": 7,
    "neptune": 8,
    "pluto": 9,
}

PLANET_ALIASES = {
    "sun": "sun",
    "moon": "moon",
    "mercury": "mercury",
    "venus": "venus",
    "mars": "mars",
    "jupiter": "jupiter",
    "saturn": "saturn",
    "uranus": "uranus",
    "neptune": "neptune",
    "pluto": "pluto",
}

ASPECTS = {
    "conjunction": 0,
    "sextile": 60,
    "square": 90,
    "trine": 120,
    "opposition": 180,
}

SIGN_TRAITS = {
    "Aries": "инициатива и прямое действие",
    "Taurus": "устойчивость и материальная опора",
    "Gemini": "общение и гибкость мышления",
    "Cancer": "эмоциональная глубина и забота",
    "Leo": "самовыражение и творческий импульс",
    "Virgo": "структура, польза и внимание к деталям",
    "Libra": "партнерство и поиск баланса",
    "Scorpio": "интенсивность и трансформация",
    "Sagittarius": "смысл, рост и расширение горизонтов",
    "Capricorn": "дисциплина и долгосрочные цели",
    "Aquarius": "оригинальность и идеи будущего",
    "Pisces": "интуиция и эмпатия",
}

SIGN_EN_RU = {
    "Aries": "Овен",
    "Taurus": "Телец",
    "Gemini": "Близнецы",
    "Cancer": "Рак",
    "Leo": "Лев",
    "Virgo": "Дева",
    "Libra": "Весы",
    "Scorpio": "Скорпион",
    "Sagittarius": "Стрелец",
    "Capricorn": "Козерог",
    "Aquarius": "Водолей",
    "Pisces": "Рыбы",
}

SIGN_RU_EN = {value: key for key, value in SIGN_EN_RU.items()}

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


def _normalize_sign_en(sign: str) -> str:
    sign_clean = str(sign or "").strip()
    if sign_clean in SIGN_EN_RU:
        return sign_clean
    if sign_clean in SIGN_RU_EN:
        return SIGN_RU_EN[sign_clean]
    title = sign_clean.title()
    if title in SIGN_EN_RU:
        return title
    return sign_clean


def _sign_ru(sign: str) -> str:
    sign_en = _normalize_sign_en(sign)
    return SIGN_EN_RU.get(sign_en, str(sign).strip())


def _aspect_ru(aspect: str) -> str:
    key = str(aspect or "").strip().lower()
    return ASPECT_LABELS_RU.get(key, key)


def _planet_ru(planet_key: str) -> str:
    key = str(planet_key or "").strip().lower()
    return PLANET_LABELS_RU.get(key, key.capitalize())



def _sign_from_longitude(longitude: float) -> str:
    idx = int((longitude % 360) // 30)
    return SIGNS[idx]



def _calc_aspects(planet_positions: dict[str, float], orb: float = 6.0) -> list[dict]:
    aspects: list[dict] = []
    for p1, p2 in combinations(planet_positions.keys(), 2):
        diff = abs(planet_positions[p1] - planet_positions[p2])
        diff = min(diff, 360 - diff)

        for aspect_name, aspect_angle in ASPECTS.items():
            delta = abs(diff - aspect_angle)
            if delta <= orb:
                aspects.append(
                    {
                        "planet_1": p1,
                        "planet_2": p2,
                        "aspect": aspect_name,
                        "orb": round(delta, 3),
                    }
                )
                break
    return aspects



def _build_interpretation(planets: dict[str, dict], rising_sign: str, aspects: list[dict]) -> dict[str, Any]:
    sun_sign_raw = planets.get("sun", {}).get("sign", "Unknown")
    moon_sign_raw = planets.get("moon", {}).get("sign", "Unknown")
    rising_sign_raw = rising_sign

    sun_sign_en = _normalize_sign_en(str(sun_sign_raw))
    moon_sign_en = _normalize_sign_en(str(moon_sign_raw))
    rising_sign_en = _normalize_sign_en(str(rising_sign_raw))

    sun_sign = _sign_ru(sun_sign_en)
    moon_sign = _sign_ru(moon_sign_en)
    rising_sign_ru = _sign_ru(rising_sign_en)

    sun_theme = SIGN_TRAITS.get(sun_sign_en, "личная стратегия развития")
    moon_theme = SIGN_TRAITS.get(moon_sign_en, "эмоциональная саморегуляция")
    rising_theme = SIGN_TRAITS.get(rising_sign_en, "первое впечатление и стиль взаимодействия")

    top_aspects = sorted(aspects, key=lambda item: item.get("orb", 999))[:3]
    aspect_lines: list[str] = []
    for item in top_aspects:
        p1 = _planet_ru(str(item.get("planet_1", "planet")))
        p2 = _planet_ru(str(item.get("planet_2", "planet")))
        asp = _aspect_ru(str(item.get("aspect", "aspect")))
        orb = item.get("orb")
        aspect_lines.append(f"{p1} - {p2}: {asp} (орб {orb})")

    summary = (
        f"Солнце в знаке {sun_sign} задает вектор через {sun_theme}. "
        f"Луна в знаке {moon_sign} показывает эмоциональные реакции через {moon_theme}. "
        f"Асцендент в знаке {rising_sign_ru} задает стиль проявления через {rising_theme}."
    )

    planets_brief: list[str] = []
    for key in PLANETS.keys():
        pdata = planets.get(key, {})
        sign_value = _sign_ru(str(pdata.get("sign", "")))
        retro = bool(pdata.get("retrograde"))
        retro_mark = ", ретроградно" if retro else ""
        longitude = pdata.get("longitude")
        if longitude is None:
            planets_brief.append(f"{_planet_ru(key)}: {sign_value}{retro_mark}")
        else:
            planets_brief.append(f"{_planet_ru(key)}: {sign_value}, {longitude}°{retro_mark}")

    return {
        "summary": summary,
        "sun_explanation": f"Солнце в {sun_sign}: {sun_theme}.",
        "moon_explanation": f"Луна в {moon_sign}: {moon_theme}.",
        "rising_explanation": f"Асцендент в {rising_sign_ru}: {rising_theme}.",
        "key_aspects": aspect_lines,
        "planets_brief": planets_brief,
        "next_steps": [
            "Выберите 1 ключевую цель на ближайшие 14 дней и фиксируйте прогресс ежедневно.",
            "Сверяйте решения с эмоциональным фоном Луны, а действия — с вектором Солнца.",
            "Используйте сильные аспекты как точки ускорения, слабые — как зоны внимания.",
        ],
    }



def _fallback_chart(profile: BirthProfile) -> dict:
    base = (
        profile.birth_date.toordinal()
        + profile.birth_time.hour * 17
        + int(profile.latitude * 10)
        + int(profile.longitude * 10)
    ) % 360

    planet_longitudes = {name: (base + idx * 27.3) % 360 for idx, name in enumerate(PLANETS.keys())}
    planet_payload = {
        name: {
            "longitude": round(lon, 5),
            "sign": _sign_ru(_sign_from_longitude(lon)),
            "sign_en": _sign_from_longitude(lon),
        }
        for name, lon in planet_longitudes.items()
    }

    house_cusps = [round((base + i * 30) % 360, 5) for i in range(12)]
    rising_sign_en = _sign_from_longitude(house_cusps[0])
    rising_sign = _sign_ru(rising_sign_en)
    aspects = _calc_aspects(planet_longitudes)

    return {
        "engine": "fallback",
        "source": "internal",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "planets": planet_payload,
        "houses": house_cusps,
        "rising_sign": rising_sign,
        "rising_sign_en": rising_sign_en,
        "aspects": aspects,
        "interpretation": _build_interpretation(planet_payload, rising_sign, aspects),
    }



def _pick_float(payload: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        if key in payload and payload[key] is not None:
            try:
                return float(payload[key])
            except (TypeError, ValueError):
                continue
    return None



def _pick_text(payload: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return None



def _normalize_astrologyapi(raw: dict[str, Any], utc_dt: datetime) -> dict | None:
    planet_longitudes: dict[str, float] = {}
    planets_payload: dict[str, dict[str, Any]] = {}

    raw_planets = raw.get("planets") if isinstance(raw, dict) else None
    if isinstance(raw_planets, list):
        for planet in raw_planets:
            if not isinstance(planet, dict):
                continue
            name_raw = _pick_text(planet, ["name", "planet", "planet_name"]) or ""
            name = PLANET_ALIASES.get(name_raw.lower())
            if not name:
                continue

            lon = _pick_float(planet, ["full_degree", "norm_degree", "normDegree", "longitude", "degree"])
            if lon is None:
                continue

            sign_raw = _pick_text(planet, ["sign", "sign_name"]) or _sign_from_longitude(lon)
            sign_en = _normalize_sign_en(sign_raw)
            retro = bool(planet.get("isRetro") or planet.get("retrograde") or planet.get("is_retro"))

            planet_longitudes[name] = lon % 360
            planets_payload[name] = {
                "longitude": round(lon % 360, 6),
                "sign": _sign_ru(sign_en),
                "sign_en": sign_en,
                "retrograde": retro,
            }

    if not planets_payload:
        return None

    houses_payload: list[float] = []
    raw_houses = raw.get("houses") if isinstance(raw, dict) else None
    if isinstance(raw_houses, list):
        for house in raw_houses[:12]:
            if isinstance(house, dict):
                deg = _pick_float(house, ["norm_degree", "normDegree", "degree", "longitude", "house_degree"])
                if deg is None:
                    continue
                houses_payload.append(round(deg % 360, 6))
            elif isinstance(house, (int, float)):
                houses_payload.append(round(float(house) % 360, 6))

    if len(houses_payload) < 12:
        houses_payload = [round((idx * 30.0) % 360.0, 6) for idx in range(12)]

    rising_sign_en = None
    ascendant = raw.get("ascendant") if isinstance(raw, dict) else None
    if isinstance(ascendant, dict):
        rising_sign_en = _normalize_sign_en(_pick_text(ascendant, ["sign", "sign_name"]) or "")

    if not rising_sign_en:
        rising_sign_en = _sign_from_longitude(houses_payload[0])
    rising_sign = _sign_ru(rising_sign_en)

    aspects_payload: list[dict[str, Any]] = []
    raw_aspects = raw.get("aspects") if isinstance(raw, dict) else None
    if isinstance(raw_aspects, list):
        for aspect in raw_aspects:
            if not isinstance(aspect, dict):
                continue
            p1 = _pick_text(aspect, ["planet_1", "planet1", "first", "p1_name"])
            p2 = _pick_text(aspect, ["planet_2", "planet2", "second", "p2_name"])
            aspect_name = _pick_text(aspect, ["aspect", "type", "aspect_name"])
            orb = _pick_float(aspect, ["orb", "diff", "delta"])
            if not (p1 and p2 and aspect_name):
                continue
            aspects_payload.append(
                {
                    "planet_1": p1.lower(),
                    "planet_2": p2.lower(),
                    "aspect": aspect_name.lower(),
                    "orb": round(float(orb or 0.0), 3),
                }
            )

    if not aspects_payload:
        aspects_payload = _calc_aspects(planet_longitudes)

    normalized = {
        "engine": "astrologyapi",
        "source": "astrologyapi.com",
        "utc_timestamp": utc_dt.isoformat(),
        "planets": planets_payload,
        "houses": houses_payload,
        "rising_sign": rising_sign,
        "rising_sign_en": rising_sign_en,
        "aspects": aspects_payload,
        "provider_raw": raw,
    }
    normalized["interpretation"] = _build_interpretation(
        planets=normalized["planets"],
        rising_sign=normalized["rising_sign"],
        aspects=normalized["aspects"],
    )
    return normalized



def _calculate_via_astrologyapi(profile: BirthProfile) -> dict | None:
    user_id = settings.astrologyapi_user_id
    api_key = settings.astrologyapi_api_key
    if not user_id or not api_key:
        return None

    local_dt = datetime.combine(profile.birth_date, profile.birth_time, tzinfo=ZoneInfo(profile.timezone))
    utc_dt = local_dt.astimezone(timezone.utc)
    offset = local_dt.utcoffset()
    tz_hours = round((offset.total_seconds() / 3600.0), 2) if offset else 0.0

    payload = {
        "day": profile.birth_date.day,
        "month": profile.birth_date.month,
        "year": profile.birth_date.year,
        "hour": profile.birth_time.hour,
        "min": profile.birth_time.minute,
        "lat": profile.latitude,
        "lon": profile.longitude,
        "tzone": tz_hours,
        "house_type": settings.astrologyapi_house_system,
    }

    base_url = settings.astrologyapi_base_url.rstrip("/")
    url = f"{base_url}/western_chart_data"

    try:
        response = httpx.post(
            url,
            json=payload,
            auth=(user_id, api_key),
            timeout=settings.astrologyapi_timeout_seconds,
        )
        response.raise_for_status()
        raw = response.json()
    except Exception:
        return None

    if isinstance(raw, list) and raw:
        candidate = raw[0]
    else:
        candidate = raw

    if not isinstance(candidate, dict):
        return None

    return _normalize_astrologyapi(candidate, utc_dt)



def _calculate_via_swisseph(profile: BirthProfile) -> dict:
    if swe is None:
        return _fallback_chart(profile)

    if settings.astrology_ephe_path:
        swe.set_ephe_path(settings.astrology_ephe_path)

    local_dt = datetime.combine(profile.birth_date, profile.birth_time, tzinfo=ZoneInfo(profile.timezone))
    utc_dt = local_dt.astimezone(timezone.utc)
    hour = utc_dt.hour + utc_dt.minute / 60 + utc_dt.second / 3600

    jd_ut = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day, hour)
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED

    planet_longitudes: dict[str, float] = {}
    planets_payload: dict[str, dict] = {}
    for name, planet_id in PLANETS.items():
        try:
            coords, _ = swe.calc_ut(jd_ut, planet_id, flags)
        except Exception:
            coords, _ = swe.calc_ut(jd_ut, planet_id, swe.FLG_MOSEPH | swe.FLG_SPEED)

        lon = float(coords[0] % 360)
        speed = float(coords[3])
        sign_en = _sign_from_longitude(lon)
        planet_longitudes[name] = lon
        planets_payload[name] = {
            "longitude": round(lon, 6),
            "sign": _sign_ru(sign_en),
            "sign_en": sign_en,
            "retrograde": speed < 0,
        }

    try:
        cusps, ascmc = swe.houses_ex(jd_ut, profile.latitude, profile.longitude, b"P")
    except Exception:
        try:
            cusps, ascmc = swe.houses(jd_ut, profile.latitude, profile.longitude, b"W")
        except Exception:
            return _fallback_chart(profile)

    if len(cusps) > 12:
        houses = [round(float(cusps[idx]), 6) for idx in range(1, 13)]
    else:
        houses = [round(float(cusp), 6) for cusp in cusps[:12]]

    rising_sign_en = _sign_from_longitude(float(ascmc[0]))
    rising_sign = _sign_ru(rising_sign_en)
    aspects = _calc_aspects(planet_longitudes)

    payload = {
        "engine": "swisseph",
        "source": "internal",
        "utc_timestamp": utc_dt.isoformat(),
        "julian_day_ut": jd_ut,
        "planets": planets_payload,
        "houses": houses,
        "rising_sign": rising_sign,
        "rising_sign_en": rising_sign_en,
        "aspects": aspects,
    }
    payload["interpretation"] = _build_interpretation(planets_payload, rising_sign, aspects)
    return payload



def calculate_natal_chart(profile: BirthProfile) -> dict:
    provider = settings.astrology_provider.lower().strip()

    if provider == "astrologyapi":
        external = _calculate_via_astrologyapi(profile)
        if external:
            return external

    return _calculate_via_swisseph(profile)
