from datetime import datetime, timezone
from itertools import combinations
from zoneinfo import ZoneInfo

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

ASPECTS = {
    "conjunction": 0,
    "sextile": 60,
    "square": 90,
    "trine": 120,
    "opposition": 180,
}


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
            "sign": _sign_from_longitude(lon),
        }
        for name, lon in planet_longitudes.items()
    }

    house_cusps = [round((base + i * 30) % 360, 5) for i in range(12)]

    return {
        "engine": "fallback",
        "utc_timestamp": datetime.now(timezone.utc).isoformat(),
        "planets": planet_payload,
        "houses": house_cusps,
        "rising_sign": _sign_from_longitude(house_cusps[0]),
        "aspects": _calc_aspects(planet_longitudes),
    }


def calculate_natal_chart(profile: BirthProfile) -> dict:
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
        planet_longitudes[name] = lon
        planets_payload[name] = {
            "longitude": round(lon, 6),
            "sign": _sign_from_longitude(lon),
            "retrograde": speed < 0,
        }

    cusps, ascmc = swe.houses_ex(jd_ut, profile.latitude, profile.longitude, b"P")
    if len(cusps) > 12:
        houses = [round(float(cusps[idx]), 6) for idx in range(1, 13)]
    else:
        houses = [round(float(cusp), 6) for cusp in cusps[:12]]

    rising_sign = _sign_from_longitude(float(ascmc[0]))

    return {
        "engine": "swisseph",
        "utc_timestamp": utc_dt.isoformat(),
        "julian_day_ut": jd_ut,
        "planets": planets_payload,
        "houses": houses,
        "rising_sign": rising_sign,
        "aspects": _calc_aspects(planet_longitudes),
    }
