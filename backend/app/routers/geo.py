from fastapi import APIRouter, Query
from pydantic import BaseModel
from timezonefinder import TimezoneFinder

router = APIRouter(prefix="/v1/geo", tags=["geo"])

_tf = TimezoneFinder()

CITIES: list[dict] = [
    # Россия
    {"name": "Москва", "lat": 55.7558, "lon": 37.6173},
    {"name": "Санкт-Петербург", "lat": 59.9343, "lon": 30.3351},
    {"name": "Новосибирск", "lat": 55.0084, "lon": 82.9357},
    {"name": "Екатеринбург", "lat": 56.8389, "lon": 60.6057},
    {"name": "Казань", "lat": 55.7887, "lon": 49.1221},
    {"name": "Нижний Новгород", "lat": 56.2965, "lon": 43.9361},
    {"name": "Челябинск", "lat": 55.1644, "lon": 61.4368},
    {"name": "Самара", "lat": 53.1959, "lon": 50.1002},
    {"name": "Омск", "lat": 54.9885, "lon": 73.3242},
    {"name": "Ростов-на-Дону", "lat": 47.2357, "lon": 39.7015},
    {"name": "Уфа", "lat": 54.7388, "lon": 55.9721},
    {"name": "Красноярск", "lat": 56.0153, "lon": 92.8932},
    {"name": "Пермь", "lat": 58.0105, "lon": 56.2502},
    {"name": "Воронеж", "lat": 51.6720, "lon": 39.1843},
    {"name": "Волгоград", "lat": 48.7080, "lon": 44.5133},
    {"name": "Краснодар", "lat": 45.0355, "lon": 38.9753},
    {"name": "Саратов", "lat": 51.5336, "lon": 46.0344},
    {"name": "Тюмень", "lat": 57.1522, "lon": 65.5272},
    {"name": "Тольятти", "lat": 53.5078, "lon": 49.4204},
    {"name": "Ижевск", "lat": 56.8527, "lon": 53.2114},
    {"name": "Барнаул", "lat": 53.3548, "lon": 83.7698},
    {"name": "Иркутск", "lat": 52.2978, "lon": 104.2964},
    {"name": "Хабаровск", "lat": 48.4827, "lon": 135.0838},
    {"name": "Владивосток", "lat": 43.1155, "lon": 131.8855},
    {"name": "Ярославль", "lat": 57.6261, "lon": 39.8845},
    {"name": "Томск", "lat": 56.4846, "lon": 84.9476},
    {"name": "Оренбург", "lat": 51.7682, "lon": 55.0969},
    {"name": "Кемерово", "lat": 55.3333, "lon": 86.0833},
    {"name": "Рязань", "lat": 54.6269, "lon": 39.6916},
    {"name": "Астрахань", "lat": 46.3497, "lon": 48.0408},
    {"name": "Тула", "lat": 54.1961, "lon": 37.6182},
    {"name": "Калининград", "lat": 54.7104, "lon": 20.4522},
    {"name": "Сочи", "lat": 43.6028, "lon": 39.7342},
    {"name": "Мурманск", "lat": 68.9585, "lon": 33.0827},
    {"name": "Архангельск", "lat": 64.5399, "lon": 40.5152},
    {"name": "Сургут", "lat": 61.2500, "lon": 73.3833},
    {"name": "Якутск", "lat": 62.0355, "lon": 129.6755},
    {"name": "Владикавказ", "lat": 43.0205, "lon": 44.6819},
    {"name": "Махачкала", "lat": 42.9849, "lon": 47.5047},
    {"name": "Грозный", "lat": 43.3125, "lon": 45.6986},
    # СНГ
    {"name": "Минск", "lat": 53.9006, "lon": 27.5590},
    {"name": "Киев", "lat": 50.4501, "lon": 30.5234},
    {"name": "Алматы", "lat": 43.2380, "lon": 76.9458},
    {"name": "Астана", "lat": 51.1694, "lon": 71.4491},
    {"name": "Ташкент", "lat": 41.2995, "lon": 69.2401},
    {"name": "Баку", "lat": 40.4093, "lon": 49.8671},
    {"name": "Тбилиси", "lat": 41.7151, "lon": 44.8271},
    {"name": "Ереван", "lat": 40.1792, "lon": 44.4991},
    {"name": "Бишкек", "lat": 42.8746, "lon": 74.5698},
    {"name": "Кишинёв", "lat": 47.0105, "lon": 28.8638},
]


class CityResult(BaseModel):
    name: str
    latitude: float
    longitude: float
    timezone: str


@router.get("/cities", response_model=list[CityResult])
def search_cities(q: str = Query(min_length=1, max_length=100)):
    query = q.lower().strip()
    results: list[CityResult] = []

    for city in CITIES:
        if query in city["name"].lower():
            tz = _tf.timezone_at(lat=city["lat"], lng=city["lon"]) or "UTC"
            results.append(
                CityResult(
                    name=city["name"],
                    latitude=city["lat"],
                    longitude=city["lon"],
                    timezone=tz,
                )
            )
        if len(results) >= 8:
            break

    return results
