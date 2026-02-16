from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger(__name__)


def llm_provider_label() -> str | None:
    provider = settings.llm_provider.lower().strip()

    if provider == "openrouter" and settings.openrouter_api_key:
        return f"openrouter:{settings.openrouter_model}"
    if provider == "gemini" and settings.gemini_api_key:
        return f"gemini:{settings.gemini_model}"
    if provider == "auto":
        if settings.openrouter_api_key:
            return f"openrouter:{settings.openrouter_model}"
        if settings.gemini_api_key:
            return f"gemini:{settings.gemini_model}"
    return None


# ── OpenRouter (OpenAI-compatible) ──────────────────────────────────

def _request_openrouter_text(prompt: str, temperature: float, max_tokens: int) -> str | None:
    api_key = settings.openrouter_api_key
    if not api_key:
        return None

    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://astrobot.app",
        "X-Title": "AstroBot",
    }
    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": "Ты профессиональный астролог и таролог. Отвечай только на русском языке. Пиши по делу, без markdown, без дисклеймеров."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        response = httpx.post(
            url,
            headers=headers,
            json=payload,
            timeout=settings.openrouter_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return None

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            return None

        message = choices[0].get("message", {})
        text = message.get("content", "")
        if isinstance(text, str) and text.strip():
            return text.strip()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:300] if exc.response is not None else ""
        logger.warning("OpenRouter request failed status=%s body=%s", exc.response.status_code, body)
    except Exception as exc:
        logger.warning("OpenRouter request failed error=%s", str(exc))
    return None


# ── Gemini ──────────────────────────────────────────────────────────

def _extract_gemini_text(payload: dict[str, Any]) -> str | None:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return None

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None


def _request_gemini_text(prompt: str, temperature: float, max_output_tokens: int) -> str | None:
    api_key = settings.gemini_api_key
    if not api_key:
        return None

    base_url = settings.gemini_base_url.rstrip("/")
    requested_model = settings.gemini_model.strip()
    models_to_try = [requested_model]
    if requested_model != "gemini-2.0-flash":
        models_to_try.append("gemini-2.0-flash")

    for model in models_to_try:
        url = f"{base_url}/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
            },
        }
        try:
            response = httpx.post(
                url,
                params={"key": api_key},
                json=payload,
                timeout=settings.gemini_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                continue
            text = _extract_gemini_text(data)
            if text:
                return text
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:250] if exc.response is not None else ""
            logger.warning("Gemini request failed for model=%s status=%s body=%s", model, exc.response.status_code, body)
            continue
        except Exception as exc:  # pragma: no cover
            logger.warning("Gemini request failed for model=%s error=%s", model, str(exc))
            continue
    return None


# ── Unified dispatcher ──────────────────────────────────────────────

def _request_llm_text(prompt: str, temperature: float, max_tokens: int) -> str | None:
    provider = settings.llm_provider.lower().strip()

    if provider == "openrouter":
        result = _request_openrouter_text(prompt, temperature, max_tokens)
        if result:
            return result
        return _request_gemini_text(prompt, temperature, max_tokens)

    if provider == "gemini":
        result = _request_gemini_text(prompt, temperature, max_tokens)
        if result:
            return result
        return _request_openrouter_text(prompt, temperature, max_tokens)

    # auto: try openrouter first, then gemini
    result = _request_openrouter_text(prompt, temperature, max_tokens)
    if result:
        return result
    return _request_gemini_text(prompt, temperature, max_tokens)


# ── Prompts & public API ────────────────────────────────────────────

def _cards_for_prompt(cards: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for card in cards:
        position = card.get("position", "?")
        slot_label = str(card.get("slot_label") or "").strip()
        card_name = str(card.get("card_name") or "").strip()
        meaning = str(card.get("meaning") or "").strip()
        is_reversed = bool(card.get("is_reversed"))
        orientation = "перевернутая" if is_reversed else "прямая"
        line = f"{position}. {slot_label} | {card_name} ({orientation}) | смысл: {meaning}"
        lines.append(line)
    return "\n".join(lines)


def fallback_tarot_interpretation(question: str | None, cards: list[dict[str, Any]]) -> str:
    if not cards:
        return "Общая энергия: сейчас важно действовать спокойно и последовательно."

    card_blocks: list[str] = []
    for idx, card in enumerate(cards[:3], start=1):
        meaning = str(card.get("meaning") or "").strip() or "прочтите карту как подсказку на текущий шаг."
        card_blocks.append(f"Карта {idx}: {meaning}")

    question_line = (
        f"Общая энергия: вопрос «{question.strip()}» лучше решать через ясные приоритеты и короткие действия."
        if question and question.strip()
        else "Общая энергия: фокус на одном главном решении дня и отказ от лишнего."
    )

    return "\n".join(
        [
            question_line,
            *card_blocks,
            "Практический шаг на 24 часа: выберите один конкретный шаг и выполните его сегодня до вечера.",
        ]
    )


def interpret_tarot_reading(question: str | None, cards: list[dict[str, Any]]) -> str | None:
    if not cards:
        return None

    prompt = (
        "Интерпретируй расклад из 3 карт таро и дай практичное объяснение.\n"
        "Не используй markdown, не используй дисклеймеры, пиши по делу.\n"
        "Формат строго:\n"
        "Общая энергия: ...\n"
        "Карта 1: ...\n"
        "Карта 2: ...\n"
        "Карта 3: ...\n"
        "Практический шаг на 24 часа: ...\n\n"
        f"Вопрос пользователя: {question or 'Без уточняющего вопроса'}\n"
        "Карты:\n"
        f"{_cards_for_prompt(cards)}"
    )

    return _request_llm_text(prompt=prompt, temperature=0.7, max_tokens=700)


def interpret_combo_insight(
    question: str | None,
    natal_summary: str,
    daily_summary: str,
    cards: list[dict[str, Any]],
) -> str | None:
    if not cards:
        return None

    prompt = (
        "Сформируй единый краткий совет, объединяющий натальную карту, прогноз дня и карты таро.\n"
        "Тон: конкретно, практично, без воды.\n"
        "Структура:\n"
        "1) Главный фокус дня (1-2 предложения)\n"
        "2) Что усилить\n"
        "3) Чего избегать\n"
        "4) Один конкретный шаг до конца дня\n\n"
        f"Вопрос: {question or 'Без вопроса'}\n"
        f"Натальный контекст: {natal_summary}\n"
        f"Прогноз дня: {daily_summary}\n"
        "Карты таро:\n"
        f"{_cards_for_prompt(cards)}"
    )

    return _request_llm_text(prompt=prompt, temperature=0.6, max_tokens=500)
