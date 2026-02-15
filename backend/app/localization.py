from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

import httpx

from .config import settings

SKIP_KEYS = {
    "id",
    "profile_id",
    "session_id",
    "reservation_id",
    "user_id",
    "owner_user_id",
    "inviter_user_id",
    "invitee_user_id",
    "token",
    "public_token",
    "invite_token",
    "slug",
    "timezone",
    "url",
    "image_url",
    "cover_url",
    "created_at",
    "birth_date",
    "birth_time",
    "date",
    "utc_timestamp",
    "julian_day_ut",
    "engine",
    "source",
    "provider",
    "provider_raw",
    "spread_type",
    "status",
}

KNOWN_TRANSLATIONS = {
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
    "conjunction": "соединение",
    "sextile": "секстиль",
    "square": "квадрат",
    "trine": "тригон",
    "opposition": "оппозиция",
    "past": "прошлое",
    "present": "настоящее",
    "future": "будущее",
    "focus": "фокус",
    "you": "вы",
    "partner": "партнер",
    "connection": "связь",
    "situation": "ситуация",
    "challenge": "вызов",
    "advice": "совет",
    "Unauthorized": "Не авторизован",
    "Not Found": "Не найдено",
}

LATIN_RE = re.compile(r"[A-Za-z]")
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
TOKENISH_RE = re.compile(r"^[A-Za-z0-9_./:=+\-]+$")


def _can_be_translated(text: str) -> bool:
    if not text:
        return False
    if CYRILLIC_RE.search(text):
        return False
    if not LATIN_RE.search(text):
        return False
    if text in KNOWN_TRANSLATIONS:
        return True

    # Keep technical tokens untouched.
    if TOKENISH_RE.fullmatch(text) and " " not in text:
        return False

    return True


@lru_cache(maxsize=4096)
def _translate_via_google_free(text: str) -> str:
    if not settings.enable_response_localization:
        return text

    if not _can_be_translated(text):
        return text

    mapped = KNOWN_TRANSLATIONS.get(text)
    if mapped:
        return mapped

    if not settings.translate_via_google_free:
        return text

    try:
        response = httpx.get(
            "https://translate.googleapis.com/translate_a/single",
            params={
                "client": "gtx",
                "sl": "auto",
                "tl": "ru",
                "dt": "t",
                "q": text,
            },
            timeout=settings.translation_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
            return text

        chunks: list[str] = []
        for item in payload[0]:
            if isinstance(item, list) and item and isinstance(item[0], str):
                chunks.append(item[0])

        translated = "".join(chunks).strip()
        return translated or text
    except Exception:
        return text


def _replace_known_terms(value: str) -> str:
    text = value
    for src, dst in KNOWN_TRANSLATIONS.items():
        if src == dst:
            continue
        if not LATIN_RE.search(src):
            continue
        pattern = re.compile(rf"(?<![A-Za-zА-Яа-яЁё]){re.escape(src)}(?![A-Za-zА-Яа-яЁё])")
        text = pattern.sub(dst, text)
    return text


def _localize_string(value: str) -> str:
    replaced = _replace_known_terms(value)
    if replaced != value:
        return replaced

    direct = KNOWN_TRANSLATIONS.get(value)
    if direct:
        return direct
    return _translate_via_google_free(value)


def localize_payload(payload: Any, key: str | None = None) -> Any:
    if key and key in SKIP_KEYS:
        return payload

    if isinstance(payload, dict):
        localized: dict[str, Any] = {}
        for k, v in payload.items():
            localized[k] = localize_payload(v, key=k)
        return localized

    if isinstance(payload, list):
        return [localize_payload(item, key=key) for item in payload]

    if isinstance(payload, str):
        return _localize_string(payload)

    return payload


def localize_json_bytes(raw: bytes) -> bytes:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return raw

    localized = localize_payload(payload)
    return json.dumps(localized, ensure_ascii=False).encode("utf-8")
