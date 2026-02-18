import json
from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel
from timezonefinder import TimezoneFinder

router = APIRouter(prefix="/v1/geo", tags=["geo"])

_tf = TimezoneFinder()

# Generated dataset (all Russian cities from ru-cities):
# https://github.com/epogrebnyak/ru-cities/blob/main/assets/towns.csv
_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_CITIES_PATH = _ASSETS_DIR / "russian_cities_all.json"
_WORLD_CITIES_PATH = _ASSETS_DIR / "world_cities.json"
_FALLBACK_CITIES: list[dict] = [
    {"name": "Москва", "lat": 55.7558, "lon": 37.6173},
    {"name": "Санкт-Петербург", "lat": 59.9343, "lon": 30.3351},
    {"name": "Новосибирск", "lat": 55.0084, "lon": 82.9357},
]
# Some timezonefinder builds return non-local but offset-equivalent timezones.
# For Russian cities we normalize to canonical Russian zones for UI clarity.
_RUSSIA_TZ_ALIAS: dict[str, str] = {
    "Africa/Johannesburg": "Europe/Kaliningrad",  # UTC+2
    "Asia/Dubai": "Europe/Samara",  # UTC+4
    "Asia/Karachi": "Asia/Yekaterinburg",  # UTC+5
    "Asia/Dhaka": "Asia/Omsk",  # UTC+6
    "Asia/Jakarta": "Asia/Krasnoyarsk",  # UTC+7
    "Asia/Manila": "Asia/Irkutsk",  # UTC+8
    "Asia/Tokyo": "Asia/Yakutsk",  # UTC+9
    "Australia/Brisbane": "Asia/Vladivostok",  # UTC+10
    "Asia/Sakhalin": "Asia/Magadan",  # UTC+11
    "Pacific/Fiji": "Asia/Kamchatka",  # UTC+12
}


def _normalize_text(value: str) -> str:
    return value.lower().replace("ё", "е").strip()


def _load_json_cities(path: Path) -> list[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    if not isinstance(payload, list):
        return []

    cleaned: list[dict] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        try:
            lat = float(item["lat"])
            lon = float(item["lon"])
        except Exception:
            continue
        timezone = str(item.get("timezone") or "").strip() or None
        name_ru = str(item.get("name_ru") or "").strip() or None
        cleaned.append({"name": name, "lat": lat, "lon": lon, "timezone": timezone, "name_ru": name_ru})

    return cleaned


def _load_cities() -> list[dict]:
    russian = _load_json_cities(_CITIES_PATH)
    world = _load_json_cities(_WORLD_CITIES_PATH)
    combined = russian + world
    return combined or _FALLBACK_CITIES


CITIES: list[dict] = _load_cities()
_CITY_POINTS: list[tuple[float, float]] = [(float(city["lat"]), float(city["lon"])) for city in CITIES]


def _is_near_russian_city(latitude: float, longitude: float, delta: float = 2.0) -> bool:
    for city_lat, city_lon in _CITY_POINTS:
        if abs(latitude - city_lat) <= delta and abs(longitude - city_lon) <= delta:
            return True
    return False


def _normalize_timezone(timezone: str, latitude: float, longitude: float) -> str:
    if timezone in _RUSSIA_TZ_ALIAS and _is_near_russian_city(latitude, longitude):
        return _RUSSIA_TZ_ALIAS[timezone]
    return timezone


class CityResult(BaseModel):
    name: str
    latitude: float
    longitude: float
    timezone: str


class TimezoneResult(BaseModel):
    timezone: str


@router.get("/cities", response_model=list[CityResult])
def search_cities(q: str = Query(min_length=1, max_length=100)):
    query = _normalize_text(q)
    results: list[CityResult] = []

    for city in CITIES:
        name_match = query in _normalize_text(city["name"])
        ru_match = city.get("name_ru") and query in _normalize_text(city["name_ru"])
        if name_match or ru_match:
            tz = city.get("timezone")
            if not tz:
                tz = _tf.timezone_at(lat=city["lat"], lng=city["lon"]) or "UTC"
                tz = _normalize_timezone(tz, city["lat"], city["lon"])
            display_name = city["name"]
            if city.get("name_ru"):
                display_name = f"{city['name_ru']} ({city['name']})"
            results.append(
                CityResult(
                    name=display_name,
                    latitude=city["lat"],
                    longitude=city["lon"],
                    timezone=tz,
                )
            )
        if len(results) >= 8:
            break

    return results


@router.get("/timezone", response_model=TimezoneResult)
def detect_timezone(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
):
    timezone = _tf.timezone_at(lat=latitude, lng=longitude) or "UTC"
    timezone = _normalize_timezone(timezone, latitude, longitude)
    return TimezoneResult(timezone=timezone)
