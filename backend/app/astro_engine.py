from datetime import datetime, timezone
from itertools import combinations
import logging
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

NODE_ALIASES = {
    "north node": "north_node",
    "northnode": "north_node",
    "true node": "north_node",
    "mean node": "north_node",
    "rahu": "north_node",
    "south node": "south_node",
    "southnode": "south_node",
    "ketu": "south_node",
}

ASPECTS = {
    "conjunction": 0,
    "sextile": 60,
    "square": 90,
    "trine": 120,
    "opposition": 180,
}

ASPECT_ALIASES = {
    "conj": "conjunction",
    "conjunction": "conjunction",
    "sext": "sextile",
    "sextile": "sextile",
    "square": "square",
    "sqr": "square",
    "quadrature": "square",
    "trine": "trine",
    "trigon": "trine",
    "opposition": "opposition",
    "opp": "opposition",
}

HOUSE_RULERS = {
    "Aries": ["mars"],
    "Taurus": ["venus"],
    "Gemini": ["mercury"],
    "Cancer": ["moon"],
    "Leo": ["sun"],
    "Virgo": ["mercury"],
    "Libra": ["venus"],
    "Scorpio": ["mars", "pluto"],
    "Sagittarius": ["jupiter"],
    "Capricorn": ["saturn"],
    "Aquarius": ["saturn", "uranus"],
    "Pisces": ["jupiter", "neptune"],
}

ESSENTIAL_DOMICILE = {
    "sun": {"Leo"},
    "moon": {"Cancer"},
    "mercury": {"Gemini", "Virgo"},
    "venus": {"Taurus", "Libra"},
    "mars": {"Aries", "Scorpio"},
    "jupiter": {"Sagittarius", "Pisces"},
    "saturn": {"Capricorn", "Aquarius"},
    "uranus": {"Aquarius"},
    "neptune": {"Pisces"},
    "pluto": {"Scorpio"},
}

ESSENTIAL_EXALTATION = {
    "sun": {"Aries"},
    "moon": {"Taurus"},
    "mercury": {"Virgo"},
    "venus": {"Pisces"},
    "mars": {"Capricorn"},
    "jupiter": {"Cancer"},
    "saturn": {"Libra"},
}

ESSENTIAL_TAG_SCORE = {
    "domicile": 5,
    "exaltation": 4,
    "detriment": -5,
    "fall": -4,
}

ESSENTIAL_TAG_RU = {
    "domicile": "обитель",
    "exaltation": "экзальтация",
    "detriment": "изгнание",
    "fall": "падение",
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

logger = logging.getLogger("astrobot.astro_engine")


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


def _normalize_aspect_name(aspect: str) -> str:
    key = str(aspect or "").strip().lower()
    return ASPECT_ALIASES.get(key, key)


def _planet_ru(planet_key: str) -> str:
    key = str(planet_key or "").strip().lower()
    return PLANET_LABELS_RU.get(key, key.capitalize())


def _normalize_longitude(value: float) -> float:
    return float(value) % 360.0


def _opposite_sign(sign_en: str) -> str:
    normalized = _normalize_sign_en(sign_en)
    try:
        idx = SIGNS.index(normalized)
    except ValueError:
        return normalized
    return SIGNS[(idx + 6) % 12]


def _house_for_longitude(longitude: float, house_cusps: list[float]) -> int:
    lon = _normalize_longitude(longitude)
    cusps = [_normalize_longitude(cusp) for cusp in house_cusps[:12]]
    if len(cusps) < 12:
        return 1

    for idx in range(12):
        start = cusps[idx]
        end = cusps[(idx + 1) % 12]
        if start <= end:
            if start <= lon < end:
                return idx + 1
        else:
            if lon >= start or lon < end:
                return idx + 1
    return 12


def _planets_in_houses(planets_payload: dict[str, dict], house_cusps: list[float]) -> dict[str, int]:
    result: dict[str, int] = {}
    for planet_key, pdata in planets_payload.items():
        if not isinstance(pdata, dict):
            continue
        lon = pdata.get("longitude")
        if lon is None:
            continue
        try:
            result[planet_key] = _house_for_longitude(float(lon), house_cusps)
        except (TypeError, ValueError):
            continue
    return result


def _build_house_rulers(house_cusps: list[float], planets_payload: dict[str, dict], planets_in_houses: dict[str, int]) -> list[dict]:
    result: list[dict] = []
    cusps = house_cusps[:12]
    for idx, cusp in enumerate(cusps, start=1):
        sign_en = _sign_from_longitude(float(cusp))
        sign_ru = _sign_ru(sign_en)
        rulers = HOUSE_RULERS.get(sign_en, [])
        ruler_payload: list[dict[str, Any]] = []
        for ruler_key in rulers:
            pdata = planets_payload.get(ruler_key) if isinstance(planets_payload, dict) else None
            if not isinstance(pdata, dict):
                continue
            ruler_payload.append(
                {
                    "planet": ruler_key,
                    "planet_ru": _planet_ru(ruler_key),
                    "in_sign": str(pdata.get("sign") or ""),
                    "in_sign_en": str(pdata.get("sign_en") or ""),
                    "in_house": planets_in_houses.get(ruler_key),
                }
            )
        result.append(
            {
                "house": idx,
                "cusp_longitude": round(float(cusp), 6),
                "cusp_sign": sign_ru,
                "cusp_sign_en": sign_en,
                "rulers": ruler_payload,
            }
        )
    return result


def _build_dispositors(planets_payload: dict[str, dict], planets_in_houses: dict[str, int]) -> list[dict]:
    def _available_rulers(sign_en: str) -> list[str]:
        return [r for r in HOUSE_RULERS.get(sign_en, []) if r in planets_payload]

    def _resolve_chain(start_planet: str) -> tuple[list[str], str | None, bool]:
        chain: list[str] = []
        visited: dict[str, int] = {}
        current = start_planet

        for _ in range(16):
            if current in visited:
                return chain, current, True
            visited[current] = len(chain)
            chain.append(current)

            pdata = planets_payload.get(current)
            if not isinstance(pdata, dict):
                break
            current_sign = _normalize_sign_en(str(pdata.get("sign_en") or pdata.get("sign") or ""))
            rulers = _available_rulers(current_sign)
            if not rulers:
                break
            next_planet = rulers[0]
            if next_planet == current:
                return chain, current, False
            current = next_planet

        final_planet = chain[-1] if chain else None
        return chain, final_planet, False

    result: list[dict] = []
    for planet_key in PLANETS.keys():
        pdata = planets_payload.get(planet_key)
        if not isinstance(pdata, dict):
            continue

        sign_en = _normalize_sign_en(str(pdata.get("sign_en") or pdata.get("sign") or ""))
        sign_ru = _sign_ru(sign_en)
        rulers = _available_rulers(sign_en)

        dispositor_items: list[dict[str, Any]] = []
        for ruler_key in rulers:
            rdata = planets_payload.get(ruler_key)
            if not isinstance(rdata, dict):
                continue
            dispositor_items.append(
                {
                    "planet": ruler_key,
                    "planet_ru": _planet_ru(ruler_key),
                    "in_sign": str(rdata.get("sign") or ""),
                    "in_sign_en": str(rdata.get("sign_en") or ""),
                    "in_house": planets_in_houses.get(ruler_key),
                }
            )

        chain, final_dispositor, is_cycle = _resolve_chain(planet_key)
        result.append(
            {
                "planet": planet_key,
                "planet_ru": _planet_ru(planet_key),
                "sign": sign_ru,
                "sign_en": sign_en,
                "in_house": planets_in_houses.get(planet_key),
                "dispositors": dispositor_items,
                "primary_dispositor": rulers[0] if rulers else None,
                "primary_dispositor_ru": _planet_ru(rulers[0]) if rulers else None,
                "chain": chain,
                "chain_ru": [_planet_ru(item) for item in chain],
                "final_dispositor": final_dispositor,
                "final_dispositor_ru": _planet_ru(final_dispositor) if final_dispositor else None,
                "is_cycle": is_cycle,
            }
        )

    return result


def _build_essential_dignities(planets_payload: dict[str, dict]) -> dict[str, Any]:
    planets_result: list[dict[str, Any]] = []
    total_score = 0

    for planet_key in PLANETS.keys():
        pdata = planets_payload.get(planet_key)
        if not isinstance(pdata, dict):
            continue

        sign_en = _normalize_sign_en(str(pdata.get("sign_en") or pdata.get("sign") or ""))
        sign_ru = _sign_ru(sign_en)
        domicile_signs = ESSENTIAL_DOMICILE.get(planet_key, set())
        exaltation_signs = ESSENTIAL_EXALTATION.get(planet_key, set())
        detriment_signs = {_opposite_sign(sign) for sign in domicile_signs}
        fall_signs = {_opposite_sign(sign) for sign in exaltation_signs}

        tags: list[str] = []
        if sign_en in domicile_signs:
            tags.append("domicile")
        if sign_en in exaltation_signs:
            tags.append("exaltation")
        if sign_en in detriment_signs:
            tags.append("detriment")
        if sign_en in fall_signs:
            tags.append("fall")

        score = sum(ESSENTIAL_TAG_SCORE.get(tag, 0) for tag in tags)
        total_score += score

        tags_ru = [ESSENTIAL_TAG_RU.get(tag, tag) for tag in tags]
        planets_result.append(
            {
                "planet": planet_key,
                "planet_ru": _planet_ru(planet_key),
                "sign": sign_ru,
                "sign_en": sign_en,
                "tags": tags if tags else ["neutral"],
                "tags_ru": tags_ru if tags_ru else ["нейтрально"],
                "score": score,
            }
        )

    strongest = sorted(planets_result, key=lambda item: item.get("score", 0), reverse=True)[:3]
    weakest = sorted(planets_result, key=lambda item: item.get("score", 0))[:3]
    return {
        "planets": planets_result,
        "total_score": total_score,
        "strongest": strongest,
        "weakest": weakest,
    }


def _aspect_lookup(aspects: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for item in aspects:
        if not isinstance(item, dict):
            continue
        p1 = str(item.get("planet_1") or "").strip().lower()
        p2 = str(item.get("planet_2") or "").strip().lower()
        aspect_name = _normalize_aspect_name(str(item.get("aspect") or ""))
        if not p1 or not p2 or p1 == p2:
            continue
        if aspect_name not in ASPECTS:
            continue
        key = tuple(sorted((p1, p2)))
        orb = item.get("orb")
        try:
            orb_value = float(orb)
        except (TypeError, ValueError):
            orb_value = 99.0
        prev = lookup.get(key)
        prev_orb = float(prev.get("orb", 99.0)) if isinstance(prev, dict) else 99.0
        if prev is None or orb_value < prev_orb:
            lookup[key] = {"aspect": aspect_name, "orb": round(orb_value, 3)}
    return lookup


def _build_configurations(
    planets_payload: dict[str, dict],
    planets_in_houses: dict[str, int],
    aspects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    planet_keys = [key for key in PLANETS.keys() if isinstance(planets_payload.get(key), dict)]
    configs: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    lookup = _aspect_lookup(aspects)

    sign_groups: dict[str, list[str]] = {}
    for planet in planet_keys:
        sign_en = _normalize_sign_en(str(planets_payload[planet].get("sign_en") or planets_payload[planet].get("sign") or ""))
        sign_groups.setdefault(sign_en, []).append(planet)
    for sign_en, members in sign_groups.items():
        if len(members) < 3:
            continue
        ordered = sorted(members, key=lambda key: PLANETS.get(key, 99))
        configs.append(
            {
                "type": "stellium_sign",
                "type_ru": "Стеллиум в знаке",
                "sign": _sign_ru(sign_en),
                "sign_en": sign_en,
                "members": ordered,
                "members_ru": [_planet_ru(item) for item in ordered],
            }
        )

    house_groups: dict[int, list[str]] = {}
    for planet in planet_keys:
        house = planets_in_houses.get(planet)
        if house is None:
            continue
        house_groups.setdefault(int(house), []).append(planet)
    for house, members in house_groups.items():
        if len(members) < 3:
            continue
        ordered = sorted(members, key=lambda key: PLANETS.get(key, 99))
        configs.append(
            {
                "type": "stellium_house",
                "type_ru": "Стеллиум в доме",
                "house": int(house),
                "members": ordered,
                "members_ru": [_planet_ru(item) for item in ordered],
            }
        )

    for a, b, c in combinations(planet_keys, 3):
        pairs = [
            (a, b, c),
            (a, c, b),
            (b, c, a),
        ]
        for p1, p2, apex in pairs:
            opp = lookup.get(tuple(sorted((p1, p2))))
            sq1 = lookup.get(tuple(sorted((p1, apex))))
            sq2 = lookup.get(tuple(sorted((p2, apex))))
            if not (opp and sq1 and sq2):
                continue
            if opp.get("aspect") != "opposition" or sq1.get("aspect") != "square" or sq2.get("aspect") != "square":
                continue
            signature = ("t_square", tuple(sorted((a, b, c))), apex)
            if signature in seen:
                continue
            seen.add(signature)
            configs.append(
                {
                    "type": "t_square",
                    "type_ru": "Т-квадрат",
                    "apex": apex,
                    "apex_ru": _planet_ru(apex),
                    "base": [p1, p2],
                    "base_ru": [_planet_ru(p1), _planet_ru(p2)],
                    "members": sorted((a, b, c), key=lambda key: PLANETS.get(key, 99)),
                    "members_ru": [_planet_ru(item) for item in sorted((a, b, c), key=lambda key: PLANETS.get(key, 99))],
                }
            )

    for a, b, c in combinations(planet_keys, 3):
        k1 = lookup.get(tuple(sorted((a, b))))
        k2 = lookup.get(tuple(sorted((a, c))))
        k3 = lookup.get(tuple(sorted((b, c))))
        if not (k1 and k2 and k3):
            continue
        if k1.get("aspect") != "trine" or k2.get("aspect") != "trine" or k3.get("aspect") != "trine":
            continue
        signature = ("grand_trine", tuple(sorted((a, b, c))))
        if signature in seen:
            continue
        seen.add(signature)
        members = sorted((a, b, c), key=lambda key: PLANETS.get(key, 99))
        configs.append(
            {
                "type": "grand_trine",
                "type_ru": "Большой тригон",
                "members": members,
                "members_ru": [_planet_ru(item) for item in members],
            }
        )

    return configs


def _mc_payload(mc_longitude: float) -> dict[str, Any]:
    mc_lon = _normalize_longitude(mc_longitude)
    mc_sign_en = _sign_from_longitude(mc_lon)
    return {
        "longitude": round(mc_lon, 6),
        "sign": _sign_ru(mc_sign_en),
        "sign_en": mc_sign_en,
    }


def _nodes_payload(north_longitude: float) -> dict[str, Any]:
    north_lon = _normalize_longitude(north_longitude)
    south_lon = _normalize_longitude(north_lon + 180.0)
    north_sign_en = _sign_from_longitude(north_lon)
    south_sign_en = _sign_from_longitude(south_lon)
    return {
        "north": {
            "longitude": round(north_lon, 6),
            "sign": _sign_ru(north_sign_en),
            "sign_en": north_sign_en,
        },
        "south": {
            "longitude": round(south_lon, 6),
            "sign": _sign_ru(south_sign_en),
            "sign_en": south_sign_en,
        },
    }


def _nodes_from_swisseph(jd_ut: float) -> dict[str, Any] | None:
    if swe is None:
        return None

    node_constant = getattr(swe, "TRUE_NODE", None)
    if node_constant is None:
        node_constant = getattr(swe, "MEAN_NODE", None)
    if node_constant is None:
        return None

    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    try:
        coords, _ = swe.calc_ut(jd_ut, node_constant, flags)
        north_lon = float(coords[0] % 360.0)
        return _nodes_payload(north_lon)
    except Exception:
        return None


def _line_for_house_ruler(item: dict[str, Any]) -> str | None:
    if not isinstance(item, dict):
        return None
    house = item.get("house")
    cusp_sign = str(item.get("cusp_sign") or "").strip()
    rulers = item.get("rulers")
    if house is None or not cusp_sign or not isinstance(rulers, list) or not rulers:
        return None

    parts: list[str] = []
    for ruler in rulers:
        if not isinstance(ruler, dict):
            continue
        pname = str(ruler.get("planet_ru") or "").strip()
        in_house = ruler.get("in_house")
        in_sign = str(ruler.get("in_sign") or "").strip()
        if not pname:
            continue
        if in_house is None:
            parts.append(f"{pname} в {in_sign}")
        else:
            parts.append(f"{pname} в {in_house} доме ({in_sign})")
    if not parts:
        return None
    return f"{house} дом в {cusp_sign}: " + ", ".join(parts)



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



def _build_interpretation(
    planets: dict[str, dict],
    rising_sign: str,
    aspects: list[dict],
    mc: dict[str, Any] | None = None,
    nodes: dict[str, Any] | None = None,
    house_rulers: list[dict[str, Any]] | None = None,
    dispositors: list[dict[str, Any]] | None = None,
    essential_dignities: dict[str, Any] | None = None,
    configurations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
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

    mc_explanation = ""
    if isinstance(mc, dict):
        mc_sign = str(mc.get("sign") or "").strip()
        if mc_sign:
            mc_explanation = (
                f"MC в знаке {mc_sign} отражает вектор социальной реализации, карьерной репутации и долгосрочных целей."
            )

    nodes_explanation = ""
    if isinstance(nodes, dict):
        north = nodes.get("north")
        south = nodes.get("south")
        if isinstance(north, dict) and isinstance(south, dict):
            nsign = str(north.get("sign") or "").strip()
            ssign = str(south.get("sign") or "").strip()
            if nsign and ssign:
                nodes_explanation = (
                    f"Северный узел в {nsign}, Южный узел в {ssign}: ось развития между привычным и новым вектором роста."
                )

    house_ruler_lines: list[str] = []
    if isinstance(house_rulers, list):
        for item in house_rulers[:6]:
            line = _line_for_house_ruler(item)
            if line:
                house_ruler_lines.append(line)

    dispositors_lines: list[str] = []
    if isinstance(dispositors, list):
        for item in dispositors[:6]:
            if not isinstance(item, dict):
                continue
            planet_ru = str(item.get("planet_ru") or "").strip()
            primary_ru = str(item.get("primary_dispositor_ru") or "").strip()
            final_ru = str(item.get("final_dispositor_ru") or "").strip()
            is_cycle = bool(item.get("is_cycle"))
            if not planet_ru:
                continue
            if is_cycle:
                dispositors_lines.append(f"{planet_ru}: цепочка диспозиторов замкнута.")
            elif primary_ru and final_ru:
                dispositors_lines.append(f"{planet_ru}: первичный диспозитор {primary_ru}, финальный — {final_ru}.")
            elif primary_ru:
                dispositors_lines.append(f"{planet_ru}: первичный диспозитор {primary_ru}.")

    dignity_lines: list[str] = []
    if isinstance(essential_dignities, dict):
        planets_dignities = essential_dignities.get("planets")
        if isinstance(planets_dignities, list):
            def _abs_score(entry: dict[str, Any]) -> float:
                raw = entry.get("score")
                try:
                    return abs(float(raw))
                except (TypeError, ValueError):
                    return 0.0

            for item in sorted(
                [entry for entry in planets_dignities if isinstance(entry, dict)],
                key=_abs_score,
                reverse=True,
            )[:5]:
                planet_ru = str(item.get("planet_ru") or "").strip()
                tags_ru = item.get("tags_ru")
                score = item.get("score")
                if not planet_ru or not isinstance(tags_ru, list):
                    continue
                tags_text = ", ".join(str(tag) for tag in tags_ru if str(tag).strip())
                dignity_lines.append(f"{planet_ru}: {tags_text} (балл {score}).")

    configuration_lines: list[str] = []
    if isinstance(configurations, list):
        for item in configurations[:6]:
            if not isinstance(item, dict):
                continue
            ctype = str(item.get("type") or "")
            ctype_ru = str(item.get("type_ru") or ctype).strip()
            members_ru = item.get("members_ru")
            if not isinstance(members_ru, list) or not members_ru:
                continue
            members_text = ", ".join(str(m) for m in members_ru if str(m).strip())
            if ctype == "stellium_sign":
                sign = str(item.get("sign") or "").strip()
                configuration_lines.append(f"{ctype_ru} ({sign}): {members_text}.")
            elif ctype == "stellium_house":
                house = item.get("house")
                configuration_lines.append(f"{ctype_ru} ({house} дом): {members_text}.")
            elif ctype == "t_square":
                apex_ru = str(item.get("apex_ru") or "").strip()
                configuration_lines.append(f"{ctype_ru}: вершина {apex_ru}; участники {members_text}.")
            else:
                configuration_lines.append(f"{ctype_ru}: {members_text}.")

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
        "mc_explanation": mc_explanation,
        "nodes_explanation": nodes_explanation,
        "house_rulers": house_ruler_lines,
        "dispositors": dispositors_lines,
        "dignities": dignity_lines,
        "configurations": configuration_lines,
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
    mc = _mc_payload(house_cusps[9] if len(house_cusps) > 9 else house_cusps[0])
    nodes = _nodes_payload((base + 123.0) % 360.0)
    planets_in_houses = _planets_in_houses(planet_payload, house_cusps)
    house_rulers = _build_house_rulers(house_cusps, planet_payload, planets_in_houses)
    dispositors = _build_dispositors(planet_payload, planets_in_houses)
    essential_dignities = _build_essential_dignities(planet_payload)
    configurations = _build_configurations(planet_payload, planets_in_houses, aspects)

    return {
        "engine": "fallback",
        "source": "internal",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "planets": planet_payload,
        "houses": house_cusps,
        "planets_in_houses": planets_in_houses,
        "rising_sign": rising_sign,
        "rising_sign_en": rising_sign_en,
        "mc": mc,
        "nodes": nodes,
        "house_rulers": house_rulers,
        "dispositors": dispositors,
        "essential_dignities": essential_dignities,
        "configurations": configurations,
        "aspects": aspects,
        "interpretation": _build_interpretation(
            planet_payload,
            rising_sign,
            aspects,
            mc=mc,
            nodes=nodes,
            house_rulers=house_rulers,
            dispositors=dispositors,
            essential_dignities=essential_dignities,
            configurations=configurations,
        ),
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
    node_longitudes: dict[str, float] = {}

    raw_planets = raw.get("planets") if isinstance(raw, dict) else None
    if isinstance(raw_planets, list):
        for planet in raw_planets:
            if not isinstance(planet, dict):
                continue
            name_raw = _pick_text(planet, ["name", "planet", "planet_name"]) or ""
            alias = name_raw.lower()
            name = PLANET_ALIASES.get(alias)
            node_name = NODE_ALIASES.get(alias)
            if not name and not node_name:
                continue

            lon = _pick_float(planet, ["full_degree", "norm_degree", "normDegree", "longitude", "degree"])
            if lon is None:
                continue

            if node_name:
                node_longitudes[node_name] = lon % 360
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
    mc_longitude = _pick_float(raw, ["mc", "midheaven", "mc_degree"])
    if mc_longitude is None:
        mc_obj = raw.get("mc") if isinstance(raw, dict) else None
        if isinstance(mc_obj, dict):
            mc_longitude = _pick_float(mc_obj, ["norm_degree", "normDegree", "degree", "longitude"])
    if mc_longitude is None:
        mc_longitude = houses_payload[9] if len(houses_payload) > 9 else houses_payload[0]
    mc = _mc_payload(mc_longitude)

    north_lon = node_longitudes.get("north_node")
    south_lon = node_longitudes.get("south_node")
    if north_lon is None and south_lon is not None:
        north_lon = (south_lon + 180.0) % 360.0
    if north_lon is not None:
        nodes = _nodes_payload(north_lon)
    else:
        nodes = None

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
            normalized_aspect = _normalize_aspect_name(aspect_name)
            if normalized_aspect not in ASPECTS:
                continue
            aspects_payload.append(
                {
                    "planet_1": p1.lower(),
                    "planet_2": p2.lower(),
                    "aspect": normalized_aspect,
                    "orb": round(float(orb or 0.0), 3),
                }
            )

    if not aspects_payload:
        aspects_payload = _calc_aspects(planet_longitudes)

    planets_in_houses = _planets_in_houses(planets_payload, houses_payload)
    house_rulers = _build_house_rulers(houses_payload, planets_payload, planets_in_houses)
    dispositors = _build_dispositors(planets_payload, planets_in_houses)
    essential_dignities = _build_essential_dignities(planets_payload)
    configurations = _build_configurations(planets_payload, planets_in_houses, aspects_payload)

    normalized = {
        "engine": "astrologyapi",
        "source": "astrologyapi.com",
        "utc_timestamp": utc_dt.isoformat(),
        "planets": planets_payload,
        "houses": houses_payload,
        "planets_in_houses": planets_in_houses,
        "rising_sign": rising_sign,
        "rising_sign_en": rising_sign_en,
        "mc": mc,
        "nodes": nodes,
        "house_rulers": house_rulers,
        "dispositors": dispositors,
        "essential_dignities": essential_dignities,
        "configurations": configurations,
        "aspects": aspects_payload,
        "provider_raw": raw,
    }
    normalized["interpretation"] = _build_interpretation(
        planets=normalized["planets"],
        rising_sign=normalized["rising_sign"],
        aspects=normalized["aspects"],
        mc=normalized.get("mc"),
        nodes=normalized.get("nodes"),
        house_rulers=normalized.get("house_rulers"),
        dispositors=normalized.get("dispositors"),
        essential_dignities=normalized.get("essential_dignities"),
        configurations=normalized.get("configurations"),
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

    asc_longitude = float(ascmc[0])
    mc_longitude = float(ascmc[1]) if len(ascmc) > 1 else asc_longitude
    rising_sign_en = _sign_from_longitude(asc_longitude)
    rising_sign = _sign_ru(rising_sign_en)
    aspects = _calc_aspects(planet_longitudes)
    mc = _mc_payload(mc_longitude)
    nodes = _nodes_from_swisseph(jd_ut)
    if nodes is None:
        nodes = _nodes_payload((asc_longitude + 120.0) % 360.0)
    planets_in_houses = _planets_in_houses(planets_payload, houses)
    house_rulers = _build_house_rulers(houses, planets_payload, planets_in_houses)
    dispositors = _build_dispositors(planets_payload, planets_in_houses)
    essential_dignities = _build_essential_dignities(planets_payload)
    configurations = _build_configurations(planets_payload, planets_in_houses, aspects)

    payload = {
        "engine": "swisseph",
        "source": "internal",
        "utc_timestamp": utc_dt.isoformat(),
        "julian_day_ut": jd_ut,
        "planets": planets_payload,
        "houses": houses,
        "planets_in_houses": planets_in_houses,
        "rising_sign": rising_sign,
        "rising_sign_en": rising_sign_en,
        "mc": mc,
        "nodes": nodes,
        "house_rulers": house_rulers,
        "dispositors": dispositors,
        "essential_dignities": essential_dignities,
        "configurations": configurations,
        "aspects": aspects,
    }
    payload["interpretation"] = _build_interpretation(
        planets_payload,
        rising_sign,
        aspects,
        mc=mc,
        nodes=nodes,
        house_rulers=house_rulers,
        dispositors=dispositors,
        essential_dignities=essential_dignities,
        configurations=configurations,
    )
    return payload



def calculate_natal_chart(profile: BirthProfile) -> dict:
    provider = settings.astrology_provider.lower().strip()

    if settings.local_only_mode:
        if provider != "swisseph":
            logger.info("LOCAL_ONLY_MODE enabled: forcing astrology provider to swisseph (was %s)", provider)
        return _calculate_via_swisseph(profile)

    if provider == "astrologyapi":
        external = _calculate_via_astrologyapi(profile)
        if external:
            return external

    if provider not in {"", "swisseph"}:
        logger.warning("Unsupported astrology_provider=%s, using swisseph", provider)

    return _calculate_via_swisseph(profile)
