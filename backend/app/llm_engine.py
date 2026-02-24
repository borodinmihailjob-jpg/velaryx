from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger(__name__)

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_OPENROUTER_FREE_TIMEOUT_SECONDS = 25.0

# Shared async HTTP client for Ollama (reused across ARQ worker calls)
_async_client: httpx.AsyncClient | None = None


def _get_async_client() -> httpx.AsyncClient:
    global _async_client
    if _async_client is None or _async_client.is_closed:
        _async_client = httpx.AsyncClient(timeout=settings.ollama_timeout_seconds)
    return _async_client


# Shared async HTTP client for OpenRouter
_openrouter_client: httpx.AsyncClient | None = None


def _get_openrouter_client() -> httpx.AsyncClient:
    global _openrouter_client
    if _openrouter_client is None or _openrouter_client.is_closed:
        _openrouter_client = httpx.AsyncClient(timeout=settings.openrouter_timeout_seconds)
    return _openrouter_client


def _sanitize_user_input(text: str, max_length: int = 500) -> str:
    """Strip control characters and cap length before injecting into LLM prompts."""
    text = _CONTROL_CHARS_RE.sub("", text)
    return text[:max_length]


INSTRUCTION_PREFIX = (
    "Ты профессиональный астролог и таролог. "
    "Отвечай только на русском языке. "
    "Пиши по делу, без markdown, без дисклеймеров."
)
INSTRUCTION_PREFIX_FREE_BASIC = (
    "Ты профессиональный астролог и таролог. "
    "Отвечай только на русском языке. "
    "Давай только базовую пользу: коротко, конкретно, без markdown и без дисклеймеров."
)
_MBTI_ARCHETYPE_DESCRIPTIONS: dict[str, str] = {
    "INTJ": "стратег-одиночка, ценит независимость и долгосрочное планирование",
    "INTP": "логик-аналитик, ищет системы и закономерности",
    "ENTJ": "командир, нацелен на эффективность и результат",
    "ENTP": "полемист, любит идеи и нестандартные решения",
    "INFJ": "провидец, глубоко интуитивен и ориентирован на смысл",
    "INFP": "медиатор, живёт ценностями и внутренней гармонией",
    "ENFJ": "протагонист, вдохновляет людей и строит связи",
    "ENFP": "активист, заряжен энтузиазмом и стремлением к новому",
    "ISTJ": "страж, надёжен и действует по проверенным правилам",
    "ISFJ": "защитник, заботится о близких и стабильности",
    "ESTJ": "администратор, структурирует мир вокруг порядка",
    "ESFJ": "консул, ориентирован на гармонию и отношения",
    "ISTP": "виртуоз, мастер практических решений здесь и сейчас",
    "ISFP": "искатель, живёт чувствами и красотой момента",
    "ESTP": "делец, действует быстро и любит риск",
    "ESFP": "артист, ищет радость и живёт в настоящем",
}

_MBTI_TONE_HINTS: dict[str, str] = {
    "INTJ": "Говори сухо и по делу, акцентируй стратегию и долгосрочную перспективу.",
    "INTP": "Используй логику и системный подход, избегай эмоциональных призывов.",
    "ENTJ": "Акцентируй цели, результаты и эффективность действий.",
    "ENTP": "Предлагай нестандартные углы зрения, провоцируй к размышлению.",
    "INFJ": "Говори о глубинных смыслах, предназначении и внутреннем пути.",
    "INFP": "Акцентируй ценности, внутренний мир и поиск подлинности.",
    "ENFJ": "Говори тепло, вдохновляй на действия через отношения и рост.",
    "ENFP": "Заряжай энтузиазмом, подчёркивай возможности и новые начинания.",
    "ISTJ": "Будь конкретен, давай чёткие рекомендации и опирайся на факты.",
    "ISFJ": "Говори тепло, акцентируй заботу о близких и стабильность.",
    "ESTJ": "Акцентируй практические шаги, порядок и конкретные задачи.",
    "ESFJ": "Говори тепло, делай акцент на отношениях и гармонии в коллективе.",
    "ISTP": "Будь лаконичен, давай практичные советы без лишних слов.",
    "ISFP": "Говори мягко, акцентируй чувства, красоту момента и саморазвитие.",
    "ESTP": "Будь динамичен, акцентируй быстрые возможности и смелые шаги.",
    "ESFP": "Говори жизнерадостно, акцентируй удовольствие от дня и общение.",
}

TAROT_MAX_TOKENS_WITH_QUESTION = 300
TAROT_MAX_TOKENS_NO_QUESTION = 160
TAROT_MAX_TOKENS_WITH_QUESTION_BASIC = 140
TAROT_MAX_TOKENS_NO_QUESTION_BASIC = 90


def llm_provider_label() -> str | None:
    provider = settings.llm_provider.lower().strip()
    if provider == "openrouter":
        models = _openrouter_text_models()
        model = models[0] if models else ""
        return f"openrouter:{model}" if model else "openrouter"
    model = settings.ollama_model.strip()
    if not model:
        return None
    return f"ollama:{model}"


def _using_openrouter() -> bool:
    return settings.llm_provider.lower().strip() == "openrouter"


def _free_basic_mode() -> bool:
    # Premium paths use dedicated OpenRouter JSON helpers and are not affected.
    return _using_openrouter()


def _json_task_max_tokens(default_tokens: int, openrouter_tokens: int) -> int:
    return openrouter_tokens if _using_openrouter() else default_tokens


def _base_instruction_prefix() -> str:
    return INSTRUCTION_PREFIX_FREE_BASIC if _free_basic_mode() else INSTRUCTION_PREFIX


def _limit_lines(lines: list[str], limit: int, compact: bool) -> list[str]:
    return lines[:limit] if compact else lines


# ── Ollama (local) ─────────────────────────────────────────────────

def _request_ollama_text(prompt: str, temperature: float, max_tokens: int) -> str | None:
    model = settings.ollama_model.strip()
    if not model:
        return None

    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": f"{_base_instruction_prefix()}\n\n{prompt}",
        "stream": False,
        # Disable "thinking" mode for models like qwen3 to ensure text lands in `response`.
        "think": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    try:
        response = httpx.post(
            url,
            json=payload,
            timeout=settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return None
        text = data.get("response")
        if isinstance(text, str) and text.strip():
            return text.strip()
    except httpx.ReadTimeout:
        logger.warning(
            "Ollama request failed model=%s error=timeout after %ss",
            model,
            settings.ollama_timeout_seconds,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else -1
        body = exc.response.text[:300] if exc.response is not None else ""
        logger.warning("Ollama request failed model=%s status=%s body=%s", model, status, body)
    except Exception as exc:
        logger.warning("Ollama request failed model=%s error=%s", model, str(exc))
    return None


# ── Async Ollama client ─────────────────────────────────────────────

async def _request_ollama_text_async(prompt: str, temperature: float, max_tokens: int) -> str | None:
    model = settings.ollama_model.strip()
    if not model:
        return None

    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": f"{_base_instruction_prefix()}\n\n{prompt}",
        "stream": False,
        # Disable "thinking" mode for models like qwen3 to ensure text lands in `response`.
        "think": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    try:
        client = _get_async_client()
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return None
        text = data.get("response")
        if isinstance(text, str) and text.strip():
            return text.strip()
    except httpx.ReadTimeout:
        logger.warning("Ollama async request failed model=%s error=timeout after %ss", model, settings.ollama_timeout_seconds)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else -1
        body = exc.response.text[:300] if exc.response is not None else ""
        logger.warning("Ollama async request failed model=%s status=%s body=%s", model, status, body)
    except Exception as exc:
        logger.warning("Ollama async request failed model=%s error=%s", model, str(exc))
    return None


def _openrouter_text_models() -> list[str]:
    raw = (settings.openrouter_free_model or settings.openrouter_model or "").strip()
    if not raw:
        return []
    # Allow configuring fallback chain: "model-a:free,model-b:free,model-c:free"
    models = [part.strip() for part in raw.replace("\n", ",").split(",")]
    return [m for m in models if m]


def _openrouter_headers() -> dict[str, str] | None:
    if not settings.openrouter_api_key:
        logger.error("OpenRouter API key not configured")
        return None
    return {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }


def _openrouter_text_payload(model: str, prompt: str, temperature: float, max_tokens: int) -> dict[str, Any]:
    return {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": _base_instruction_prefix()},
            {"role": "user", "content": prompt},
        ],
    }


def _extract_openrouter_text_response(data: Any) -> str | None:
    try:
        text = data["choices"][0]["message"]["content"]
    except Exception:
        return None
    if isinstance(text, list):
        chunks: list[str] = []
        for item in text:
            if isinstance(item, dict):
                part = item.get("text")
                if isinstance(part, str) and part.strip():
                    chunks.append(part.strip())
        if chunks:
            return "\n".join(chunks).strip()
    if isinstance(text, str) and text.strip():
        return text.strip()
    return None


def _request_openrouter_text(prompt: str, temperature: float, max_tokens: int) -> str | None:
    headers = _openrouter_headers()
    models = _openrouter_text_models()
    if not models:
        logger.error("OpenRouter free/text model is not configured")
        return None
    if not headers:
        return None

    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    timeout = min(float(settings.openrouter_timeout_seconds), _OPENROUTER_FREE_TIMEOUT_SECONDS)
    for model in models:
        payload = _openrouter_text_payload(model, prompt, temperature, max_tokens)
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            text = _extract_openrouter_text_response(data)
            if text:
                return text
            logger.warning("OpenRouter text empty response | model=%s", model)
        except httpx.ReadTimeout:
            logger.warning("OpenRouter text timeout after %.0fs | model=%s", timeout, model)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else -1
            body = exc.response.text[:300] if exc.response is not None else ""
            logger.warning("OpenRouter text HTTP error | status=%s | model=%s | body=%s", status, model, body)
        except Exception as exc:
            logger.warning("OpenRouter text request failed | model=%s | err=%s", model, exc)
    return None


async def _request_openrouter_text_async(prompt: str, temperature: float, max_tokens: int) -> str | None:
    headers = _openrouter_headers()
    models = _openrouter_text_models()
    if not models:
        logger.error("OpenRouter free/text model is not configured")
        return None
    if not headers:
        return None

    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    timeout = min(float(settings.openrouter_timeout_seconds), _OPENROUTER_FREE_TIMEOUT_SECONDS)
    client = _get_openrouter_client()
    for model in models:
        payload = _openrouter_text_payload(model, prompt, temperature, max_tokens)
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            text = _extract_openrouter_text_response(data)
            if text:
                return text
            logger.warning("OpenRouter text async empty response | model=%s", model)
        except httpx.ReadTimeout:
            logger.warning("OpenRouter text async timeout after %.0fs | model=%s", timeout, model)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else -1
            body = exc.response.text[:300] if exc.response is not None else ""
            logger.warning("OpenRouter text async HTTP error | status=%s | model=%s | body=%s", status, model, body)
        except Exception as exc:
            logger.warning("OpenRouter text async request failed | model=%s | err=%s", model, exc)
    return None


async def _request_llm_text_async(prompt: str, temperature: float, max_tokens: int) -> str | None:
    provider = settings.llm_provider.lower().strip()
    started_at = time.time()
    logger.info("LLM async request | provider=%s", provider or "ollama")

    if provider == "openrouter":
        result = await _request_openrouter_text_async(prompt, temperature, max_tokens)
    else:
        if provider and provider != "ollama":
            logger.warning("Unsupported llm_provider=%s, using ollama only", provider)
        result = await _request_ollama_text_async(prompt, temperature, max_tokens)

    elapsed = time.time() - started_at
    if result:
        logger.info("LLM async success | provider=%s | time=%.2fs", provider or "ollama", elapsed)
        return result
    logger.error("LLM async FAILED | provider=%s | time=%.2fs", provider or "ollama", elapsed)
    return None


# ── Unified dispatcher ──────────────────────────────────────────────

def _request_llm_text(prompt: str, temperature: float, max_tokens: int) -> str | None:
    provider = settings.llm_provider.lower().strip()
    started_at = time.time()

    if provider == "openrouter":
        logger.info("LLM request | provider=openrouter")
        result = _request_openrouter_text(prompt, temperature, max_tokens)
    else:
        if provider and provider != "ollama":
            logger.warning("Unsupported llm_provider=%s, using ollama only", provider)
        logger.info("LLM request | provider=ollama")
        result = _request_ollama_text(prompt, temperature, max_tokens)
    if result:
        elapsed = time.time() - started_at
        logger.info(f"LLM success | provider={(provider or 'ollama')} | time={elapsed:.2f}s")
        return result

    elapsed = time.time() - started_at
    logger.error(f"LLM FAILED | provider={(provider or 'ollama')} | time={elapsed:.2f}s")
    return None


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


def _card_name_with_orientation(card: dict[str, Any]) -> str:
    card_name = str(card.get("card_name") or "").strip() or "Без названия"
    is_reversed = bool(card.get("is_reversed"))
    orientation = "перевернутая" if is_reversed else "прямая"
    return f"{card_name} ({orientation})"


def _tarot_input_params(question: str | None, cards: list[dict[str, Any]]) -> tuple[str, str, str, str]:
    cards_sorted = sorted(cards, key=lambda c: int(c.get("position", 0) or 0))[:3]
    question_text = question.strip() if question and question.strip() else "Без уточняющего вопроса"

    card_lines: list[str] = []
    for idx in range(3):
        if idx < len(cards_sorted):
            card = cards_sorted[idx]
            card_name = _card_name_with_orientation(card)
            meaning = str(card.get("meaning") or "").strip() or "Описание отсутствует."
            card_lines.append(f"{card_name}; {meaning}")
        else:
            card_lines.append("Карта не получена; Описание отсутствует.")

    return question_text, card_lines[0], card_lines[1], card_lines[2]


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

    user_question, card_1, card_2, card_3 = _tarot_input_params(question=question, cards=cards)
    has_explicit_question = bool(question and question.strip())
    compact = _free_basic_mode()
    if compact:
        max_tokens = (
            TAROT_MAX_TOKENS_WITH_QUESTION_BASIC if has_explicit_question else TAROT_MAX_TOKENS_NO_QUESTION_BASIC
        )
        response_size_hint = "2-3 коротких абзаца, до 550 символов"
    else:
        max_tokens = TAROT_MAX_TOKENS_WITH_QUESTION if has_explicit_question else TAROT_MAX_TOKENS_NO_QUESTION
        response_size_hint = "5-8 абзацев, до 1400 символов" if has_explicit_question else "3-5 абзацев, до 900 символов"
    safe_question = _sanitize_user_input(user_question) if has_explicit_question else user_question
    question_context = (
        f"Вопрос пользователя: {safe_question}"
        if has_explicit_question
        else "Явный вопрос не задан. Дай общий ориентир на ближайшие сутки."
    )
    if compact:
        prompt = (
            "Дай базовую интерпретацию расклада простым и полезным языком.\n"
            "Без списков, без мистификации, без обещаний результата.\n"
            "Структура: краткий вывод + один практический шаг на сегодня.\n"
            f"Размер ответа: {response_size_hint}.\n\n"
            f"{question_context}\n"
            f"Карта 1: {card_1}\n"
            f"Карта 2: {card_2}\n"
            f"Карта 3: {card_3}"
        )
    else:
        prompt = (
            "Ты профессиональный таролог. "
            "Отвечай только на русском, без markdown и без списков. "
            "Дай связную, практичную и образную интерпретацию без штампов.\n\n"
            "Структура: 1) контекст, 2) связка трёх карт, 3) скрытый смысл, 4) мягкий совет.\n"
            "Не обещай гарантированных исходов. Без мед/юр рекомендаций.\n"
            f"Размер ответа: {response_size_hint}.\n\n"
            f"{question_context}\n"
            f"Карта 1 (название + описание): {card_1}\n"
            f"Карта 2 (название + описание): {card_2}\n"
            f"Карта 3 (название + описание): {card_3}"
        )

    return _request_llm_text(prompt=prompt, temperature=0.6, max_tokens=max_tokens)


# ── Premium tarot (OpenRouter Gemini) ────────────────────────────────

_PREMIUM_TAROT_SYSTEM_PROMPT = (
    "Ты профессиональный таролог. Давай глубокую интерпретацию расклада на русском языке. "
    "Отвечай ТОЛЬКО валидным JSON строго по заданной схеме. "
    "Без markdown, без пояснений вне JSON, без дополнительных ключей."
)

_PREMIUM_TAROT_SCHEMA = (
    '{\n'
    '  "question_reflection": "string 50-70 слов — переосмысление вопроса, его суть и скрытый пласт",\n'
    '  "card_analyses": [\n'
    '    {\n'
    '      "position_label": "слот расклада (напр. Прошлое / Настоящее / Будущее)",\n'
    '      "card_name": "название карты",\n'
    '      "orientation": "прямая или перевёрнутая",\n'
    '      "deep_reading": "string 120-150 слов — глубокое прочтение карты в контексте вопроса"\n'
    '    }\n'
    '  ],\n'
    '  "synthesis": "string 150-200 слов — общее послание: как карты связаны между собой",\n'
    '  "key_themes": ["тема 1 (2-4 слова)", "тема 2", "тема 3"],\n'
    '  "advice": "string 80-100 слов — практический совет: что делать, чего избегать",\n'
    '  "energy": "string 40-60 слов — энергетика момента и лучшее время для действия"\n'
    '}\n'
    'card_analyses: ровно по одному объекту на каждую карту расклада. key_themes: ровно 3 элемента.'
)

_PREMIUM_TAROT_REQUIRED_KEYS = frozenset({
    "question_reflection", "card_analyses", "synthesis", "key_themes", "advice", "energy",
})


async def interpret_tarot_premium_async(
    *,
    question: str | None,
    cards: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Premium tarot interpretation via OpenRouter Gemini. Returns structured JSON or None."""
    question_text = question.strip() if question and question.strip() else "Без уточняющего вопроса"
    card_lines: list[str] = []
    for card in sorted(cards, key=lambda c: int(c.get("position", 0) or 0)):
        orientation = "перевёрнутая" if card.get("is_reversed") else "прямая"
        slot = str(card.get("slot_label") or "").strip() or f"Позиция {card.get('position', '?')}"
        name = str(card.get("card_name") or "").strip() or "Без названия"
        meaning = str(card.get("meaning") or "").strip()
        card_lines.append(f"Позиция «{slot}» | {name} ({orientation}) | {meaning}")

    user_prompt = (
        f"Вопрос: {question_text}\n\n"
        f"Карты:\n" + "\n".join(card_lines) +
        f"\n\nСхема ответа:\n{_PREMIUM_TAROT_SCHEMA}"
    )

    raw = await _request_openrouter_json_async(
        system_prompt=_PREMIUM_TAROT_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=1800,
        temperature=0.6,
    )
    if not raw or not _PREMIUM_TAROT_REQUIRED_KEYS.issubset(raw.keys()):
        return None
    if not isinstance(raw.get("card_analyses"), list) or not raw["card_analyses"]:
        return None
    if not isinstance(raw.get("key_themes"), list) or len(raw["key_themes"]) < 3:
        return None
    return raw


def _normalize_story_animation(value: Any) -> str:
    raw = str(value or "").strip().lower()
    aliases = {
        "shine": "glow",
        "glow": "glow",
        "pulse": "pulse",
        "breathe": "pulse",
        "float": "float",
        "drift": "float",
        "orbit": "orbit",
        "swirl": "orbit",
    }
    return aliases.get(raw, "glow")


def _normalize_story_slides(payload: dict[str, Any]) -> list[dict[str, str]]:
    raw_slides = payload.get("slides")
    if not isinstance(raw_slides, list):
        return []

    normalized: list[dict[str, str]] = []
    for item in raw_slides[:6]:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or "").strip()
        body = str(item.get("body") or "").strip()
        if not title or not body:
            continue

        slide: dict[str, str] = {
            "title": title,
            "body": body,
            "animation": _normalize_story_animation(item.get("animation")),
        }

        for optional_key in ("badge", "tip", "avoid", "timing"):
            value = item.get(optional_key)
            if isinstance(value, str) and value.strip():
                slide[optional_key] = value.strip()

        normalized.append(slide)

    return normalized


def interpret_forecast_stories(
    *,
    sun_sign: str,
    moon_sign: str,
    rising_sign: str,
    energy_score: int,
    mood: str,
    focus: str,
    natal_summary: str,
    key_aspects: list[str],
    mbti_type: str | None = None,
) -> list[dict[str, str]] | None:
    compact = _free_basic_mode()
    safe_natal_summary = _sanitize_user_input(natal_summary, max_length=350 if compact else 800) if natal_summary else ""
    mbti_line = ""
    if mbti_type and mbti_type in _MBTI_ARCHETYPE_DESCRIPTIONS:
        mbti_line = (
            f"Архетип разума (MBTI): {mbti_type} — {_MBTI_ARCHETYPE_DESCRIPTIONS[mbti_type]}\n"
            f"{_MBTI_TONE_HINTS.get(mbti_type, '')}\n"
        )
    if compact:
        prompt = (
            "Собери базовые сторис на день. Только русский язык. Верни только JSON.\n"
            'Формат: {"slides":[{"title":"...","body":"1-2 коротких предложения","badge":"коротко","tip":"короткий шаг","avoid":"коротко","timing":"коротко","animation":"glow|pulse|float|orbit"}]}\n'
            "Сделай ровно 4 слайда: день, работа/деньги, отношения, самочувствие.\n"
            "Тон: практично и кратко, без мистификации.\n"
            "Каждый body до 180 символов.\n\n"
            f"{mbti_line}"
            f"Солнце: {sun_sign}; Луна: {moon_sign}; Асцендент: {rising_sign}\n"
            f"Энергия: {energy_score}/100; Режим: {mood}; Фокус: {focus}\n"
            f"Натальный контекст: {safe_natal_summary or 'Нет данных'}\n"
            f"Аспекты: {', '.join(key_aspects[:3]) if key_aspects else 'Нет данных'}"
        )
    else:
        prompt = (
            "Собери персональный сторис-пак на один день в стиле практичного гороскопа.\n"
            "Нужен только русский язык, без markdown.\n"
            "Тон: конкретно, применимо в течение дня, без воды.\n"
            "Не обещай 100% исходов и не используй мистические формулировки.\n\n"
            "Верни СТРОГО JSON-объект:\n"
            "{\n"
            '  "slides": [\n'
            "    {\n"
            '      "title": \"...\",\n'
            '      "body": \"2-3 коротких предложения\",\n'
            '      "badge": \"короткая метка\",\n'
            '      "tip": \"практический шаг до конца дня\",\n'
            '      "avoid": \"чего избегать сегодня\",\n'
            '      "timing": \"лучшее окно по времени\",\n'
            '      "animation": \"одно из: glow, pulse, float, orbit\"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Сделай 4 слайда:\n"
            "1) Общая энергия и фокус дня.\n"
            "2) Работа/деньги.\n"
            "3) Общение/отношения.\n"
            "4) Самочувствие и восстановление.\n\n"
            f"{mbti_line}"
            f"Солнце: {sun_sign}\n"
            f"Луна: {moon_sign}\n"
            f"Асцендент: {rising_sign}\n"
            f"Энергия: {energy_score}/100\n"
            f"Режим дня: {mood}\n"
            f"Фокус дня: {focus}\n"
            f"Натальный контекст: {safe_natal_summary or 'Нет данных'}\n"
            "Ключевые аспекты:\n"
            f"{chr(10).join(key_aspects[:4]) if key_aspects else 'Нет данных'}"
        )

    raw = _request_llm_text(
        prompt=prompt,
        temperature=0.55,
        max_tokens=_json_task_max_tokens(180, 420),
    )
    if not raw:
        return None

    payload = _extract_json_dict(raw)
    if not payload:
        return None

    slides = _normalize_story_slides(payload)
    if len(slides) < 3:
        return None
    return slides


def _extract_json_dict(text: str) -> dict[str, Any] | None:
    if not text:
        return None

    candidates = [text.strip()]
    cleaned = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    if cleaned:
        candidates.append(cleaned)

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidates.append(match.group(0).strip())

    for candidate in candidates:
        if not candidate:
            continue
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload

    return None


def interpret_natal_sections(
    *,
    sun_sign: str,
    moon_sign: str,
    rising_sign: str,
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
) -> dict[str, str] | None:
    compact = _free_basic_mode()
    safe_natal_summary = _sanitize_user_input(natal_summary, max_length=400 if compact else 800) if natal_summary else ""
    key_aspects_in = _limit_lines(key_aspects, 4, compact)
    planetary_profile_in = _limit_lines(planetary_profile, 6, compact)
    house_cusps_in = _limit_lines(house_cusps, 6, compact)
    planets_in_houses_in = _limit_lines(planets_in_houses, 6, compact)
    house_rulers_in = _limit_lines(house_rulers, 4, compact)
    dispositors_in = _limit_lines(dispositors, 4, compact)
    essential_dignities_in = _limit_lines(essential_dignities, 4, compact)
    configurations_in = _limit_lines(configurations, 4, compact)
    full_aspects_in = _limit_lines(full_aspects, 6, compact)
    block_size_rule = (
        "Значение каждого ключа — 1-2 коротких предложения (базовая суть + 1 практический ориентир).\n"
        "Каждый блок до ~220 символов.\n"
        if compact
        else "Значение каждого ключа — строка из 3-6 предложений.\n"
        "В каждом блоке добавь хотя бы 1 практический ориентир: что усилить/чего избегать.\n"
    )
    prompt = (
        "Ты опытный практикующий астролог. На входе факты натальной карты.\n"
        "Нужно выдать понятные и полезные интерпретации на русском языке.\n"
        "Тон: конкретный, спокойный, прикладной. Без мистификации и без воды.\n"
        "Не давай дисклеймеров, не упоминай ИИ, не используй markdown.\n\n"
        "Верни СТРОГО JSON-объект с 10 ключами:\n"
        "key_aspects, planetary_profile, house_cusps, mc_axis, lunar_nodes, house_rulers, dispositors, essential_dignities, configurations, natal_explanation.\n"
        f"{block_size_rule}"
        "Без дополнительных ключей и без обрамляющего текста.\n\n"
        f"Солнце: {sun_sign}\n"
        f"Луна: {moon_sign}\n"
        f"Асцендент: {rising_sign}\n"
        f"Краткий натальный контекст: {safe_natal_summary or 'Нет данных'}\n\n"
        "Ключевые аспекты:\n"
        f"{chr(10).join(key_aspects_in) if key_aspects_in else 'Нет данных'}\n\n"
        "Планетный профиль:\n"
        f"{chr(10).join(planetary_profile_in) if planetary_profile_in else 'Нет данных'}\n\n"
        "Куспиды домов:\n"
        f"{chr(10).join(house_cusps_in) if house_cusps_in else 'Нет данных'}\n\n"
        "Планеты в домах:\n"
        f"{chr(10).join(planets_in_houses_in) if planets_in_houses_in else 'Нет данных'}\n\n"
        "MC:\n"
        f"{mc_line or 'Нет данных'}\n\n"
        "Лунные узлы:\n"
        f"{nodes_line or 'Нет данных'}\n\n"
        "Управители домов:\n"
        f"{chr(10).join(house_rulers_in) if house_rulers_in else 'Нет данных'}\n\n"
        "Диспозиторы:\n"
        f"{chr(10).join(dispositors_in) if dispositors_in else 'Нет данных'}\n\n"
        "Эссенциальные достоинства:\n"
        f"{chr(10).join(essential_dignities_in) if essential_dignities_in else 'Нет данных'}\n\n"
        "Конфигурации карты:\n"
        f"{chr(10).join(configurations_in) if configurations_in else 'Нет данных'}\n\n"
        "Полная матрица аспектов:\n"
        f"{chr(10).join(full_aspects_in) if full_aspects_in else 'Нет данных'}"
    )

    raw = _request_llm_text(
        prompt=prompt,
        temperature=0.45,
        max_tokens=_json_task_max_tokens(220, 800),
    )
    if not raw:
        return None

    payload = _extract_json_dict(raw)
    if not payload:
        return None

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

    return result or None


# ── Async public API (used by ARQ workers) ──────────────────────────

async def interpret_natal_sections_async(
    *,
    sun_sign: str,
    moon_sign: str,
    rising_sign: str,
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
) -> dict[str, str] | None:
    compact = _free_basic_mode()
    safe_natal_summary = _sanitize_user_input(natal_summary, max_length=400 if compact else 800) if natal_summary else ""
    key_aspects_in = _limit_lines(key_aspects, 4, compact)
    planetary_profile_in = _limit_lines(planetary_profile, 6, compact)
    house_cusps_in = _limit_lines(house_cusps, 6, compact)
    planets_in_houses_in = _limit_lines(planets_in_houses, 6, compact)
    house_rulers_in = _limit_lines(house_rulers, 4, compact)
    dispositors_in = _limit_lines(dispositors, 4, compact)
    essential_dignities_in = _limit_lines(essential_dignities, 4, compact)
    configurations_in = _limit_lines(configurations, 4, compact)
    full_aspects_in = _limit_lines(full_aspects, 6, compact)
    block_size_rule = (
        "Значение каждого ключа — 1-2 коротких предложения (базовая суть + 1 практический ориентир).\n"
        "Каждый блок до ~220 символов.\n"
        if compact
        else "Значение каждого ключа — строка из 3-6 предложений.\n"
        "В каждом блоке добавь хотя бы 1 практический ориентир: что усилить/чего избегать.\n"
    )
    prompt = (
        "Ты опытный практикующий астролог. На входе факты натальной карты.\n"
        "Нужно выдать понятные и полезные интерпретации на русском языке.\n"
        "Тон: конкретный, спокойный, прикладной. Без мистификации и без воды.\n"
        "Не давай дисклеймеров, не упоминай ИИ, не используй markdown.\n\n"
        "Верни СТРОГО JSON-объект с 10 ключами:\n"
        "key_aspects, planetary_profile, house_cusps, mc_axis, lunar_nodes, house_rulers, dispositors, essential_dignities, configurations, natal_explanation.\n"
        f"{block_size_rule}"
        "Без дополнительных ключей и без обрамляющего текста.\n\n"
        f"Солнце: {sun_sign}\n"
        f"Луна: {moon_sign}\n"
        f"Асцендент: {rising_sign}\n"
        f"Краткий натальный контекст: {safe_natal_summary or 'Нет данных'}\n\n"
        "Ключевые аспекты:\n"
        f"{chr(10).join(key_aspects_in) if key_aspects_in else 'Нет данных'}\n\n"
        "Планетный профиль:\n"
        f"{chr(10).join(planetary_profile_in) if planetary_profile_in else 'Нет данных'}\n\n"
        "Куспиды домов:\n"
        f"{chr(10).join(house_cusps_in) if house_cusps_in else 'Нет данных'}\n\n"
        "Планеты в домах:\n"
        f"{chr(10).join(planets_in_houses_in) if planets_in_houses_in else 'Нет данных'}\n\n"
        "MC:\n"
        f"{mc_line or 'Нет данных'}\n\n"
        "Лунные узлы:\n"
        f"{nodes_line or 'Нет данных'}\n\n"
        "Управители домов:\n"
        f"{chr(10).join(house_rulers_in) if house_rulers_in else 'Нет данных'}\n\n"
        "Диспозиторы:\n"
        f"{chr(10).join(dispositors_in) if dispositors_in else 'Нет данных'}\n\n"
        "Эссенциальные достоинства:\n"
        f"{chr(10).join(essential_dignities_in) if essential_dignities_in else 'Нет данных'}\n\n"
        "Конфигурации карты:\n"
        f"{chr(10).join(configurations_in) if configurations_in else 'Нет данных'}\n\n"
        "Полная матрица аспектов:\n"
        f"{chr(10).join(full_aspects_in) if full_aspects_in else 'Нет данных'}"
    )

    raw = await _request_llm_text_async(
        prompt=prompt,
        temperature=0.45,
        max_tokens=_json_task_max_tokens(220, 800),
    )
    if not raw:
        return None

    payload = _extract_json_dict(raw)
    if not payload:
        return None

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

    return result or None


# ── Numerology async interpretation ─────────────────────────────────

_NUMEROLOGY_ARCHETYPES: dict[int, str] = {
    1: "Лидер, первопроходец, независимость",
    2: "Дипломат, партнёрство, чувствительность",
    3: "Творец, самовыражение, оптимизм",
    4: "Строитель, стабильность, дисциплина",
    5: "Свобода, перемены, авантюризм",
    6: "Гармония, забота, ответственность",
    7: "Мистик, анализ, духовный поиск",
    8: "Власть, амбиции, материальный успех",
    9: "Мудрец, альтруизм, завершение цикла",
    11: "Мастер-интуит, вдохновение, духовное просветление",
    22: "Мастер-строитель, великие свершения, мировой масштаб",
    33: "Мастер-учитель, сострадание, бескорыстное служение",
}


async def interpret_numerology_async(
    *,
    full_name: str,
    birth_date: str,
    life_path: int,
    expression: int,
    soul_urge: int,
    personality: int,
    birthday: int,
    personal_year: int,
) -> dict[str, str] | None:
    """Generate LLM interpretation for all 6 numerology numbers.

    Returns a dict with keys: life_path, expression, soul_urge, personality,
    birthday, personal_year. Each value is a 3-5 sentence Russian interpretation.
    Returns None if LLM call fails (caller uses static fallback).
    """
    safe_name = _sanitize_user_input(full_name, max_length=200)

    def _arch(n: int) -> str:
        return _NUMEROLOGY_ARCHETYPES.get(n, "")
    compact = _free_basic_mode()

    master_nums = [n for n in (life_path, expression, soul_urge, personality, birthday, personal_year)
                   if n in {11, 22, 33}]
    master_note = (
        f"Обрати особое внимание: числа {', '.join(str(n) for n in master_nums)} "
        "являются мастер-числами — отметь их усиленный потенциал.\n"
        if master_nums else ""
    )

    if compact:
        prompt = (
            "Ты нумеролог. Дай базовую интерпретацию чисел простым и полезным языком.\n"
            "Только русский язык. Верни только JSON без markdown.\n"
            f"{master_note}"
            "JSON-ключи: life_path, expression, soul_urge, personality, birthday, personal_year.\n"
            "Каждое значение: 1-2 коротких предложения (суть + один практический совет), до ~180 символов.\n\n"
            f"Имя: {safe_name}\n"
            f"Дата рождения: {birth_date}\n"
            f"life_path={life_path} ({_arch(life_path)})\n"
            f"expression={expression} ({_arch(expression)})\n"
            f"soul_urge={soul_urge} ({_arch(soul_urge)})\n"
            f"personality={personality} ({_arch(personality)})\n"
            f"birthday={birthday} ({_arch(birthday)})\n"
            f"personal_year={personal_year} ({_arch(personal_year)})\n"
        )
    else:
        prompt = (
            "Ты профессиональный нумеролог с глубоким знанием Пифагорейской нумерологии. "
            "Отвечай только на русском языке, без markdown, без дисклеймеров, без упоминания ИИ.\n"
            "Тон: мистический, но прикладной — каждое число должно давать практический ориентир.\n\n"
            f"{master_note}"
            "Верни СТРОГО JSON-объект с 6 ключами:\n"
            "life_path, expression, soul_urge, personality, birthday, personal_year.\n"
            "Значение каждого ключа — строка из 3-5 предложений на русском.\n"
            "Включи: суть числа, сильные стороны, вызов/тень, практический совет.\n"
            "Без дополнительных ключей и без обрамляющего текста.\n\n"
            f"Имя: {safe_name}\n"
            f"Дата рождения: {birth_date}\n\n"
            f"Число Жизненного Пути: {life_path} ({_arch(life_path)})\n"
            f"Число Выражения (Судьбы): {expression} ({_arch(expression)})\n"
            f"Число Души: {soul_urge} ({_arch(soul_urge)})\n"
            f"Число Личности: {personality} ({_arch(personality)})\n"
            f"Число Дня Рождения: {birthday} ({_arch(birthday)})\n"
            f"Число Личного Года: {personal_year} ({_arch(personal_year)})\n"
        )

    raw = await _request_llm_text_async(
        prompt=prompt,
        temperature=0.55,
        max_tokens=_json_task_max_tokens(180, 520),
    )
    if not raw:
        return None

    payload = _extract_json_dict(raw)
    if not payload:
        return None

    result: dict[str, str] = {}
    for key in ("life_path", "expression", "soul_urge", "personality", "birthday", "personal_year"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()

    return result if len(result) >= 4 else None


# ── OpenRouter (cloud LLM, premium features) ────────────────────────

async def _request_openrouter_json_async(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
) -> dict[str, Any] | None:
    """Call OpenRouter chat completions with JSON response format.

    Returns parsed JSON dict or None on any error.
    """
    if not settings.openrouter_api_key:
        logger.error("OpenRouter API key not configured")
        return None

    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.openrouter_model,
        "response_format": {"type": "json_object"},
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        started_at = time.time()
        client = _get_openrouter_client()
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        elapsed = time.time() - started_at
        logger.info("OpenRouter success | model=%s | time=%.2fs", settings.openrouter_model, elapsed)
        return _extract_json_dict(text)
    except httpx.ReadTimeout:
        logger.error("OpenRouter timeout after %.0fs | model=%s", settings.openrouter_timeout_seconds, settings.openrouter_model)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else -1
        body = exc.response.text[:300] if exc.response is not None else ""
        logger.error("OpenRouter HTTP error | status=%s | body=%s", status, body)
    except Exception as exc:
        logger.error("OpenRouter request failed: %s", exc)
    return None


_PREMIUM_NATAL_SYSTEM_PROMPT = (
    "Ты профессиональный астролог. Давай глубокий точный анализ натальной карты на русском языке. "
    "Отвечай ТОЛЬКО валидным JSON строго по заданной схеме. "
    "Без markdown, без пояснений вне JSON, без дополнительных ключей."
)

_PREMIUM_NATAL_SCHEMA = (
    '{\n'
    '  "overview": "string 90-110 слов — общий портрет личности",\n'
    '  "sun_analysis": "string 60-70 слов — Солнце: суть, мотивация, самовыражение",\n'
    '  "moon_analysis": "string 60-70 слов — Луна: эмоции, потребности, привычки",\n'
    '  "rising_analysis": "string 60-70 слов — Асцендент: маска, первое впечатление, тело",\n'
    '  "career": "string 60-70 слов — карьера, призвание, реализация",\n'
    '  "love": "string 60-70 слов — отношения, партнёрство, любовь",\n'
    '  "finance": "string 50-60 слов — деньги, ресурсы, материальный мир",\n'
    '  "health": "string 50-60 слов — здоровье, тело, энергия",\n'
    '  "growth": "string 50-60 слов — личностный рост, вызов, трансформация",\n'
    '  "strengths": ["строка 5-8 слов", "строка", "строка", "строка", "строка", "строка"],\n'
    '  "challenges": ["строка 5-8 слов", "строка", "строка", "строка"],\n'
    '  "aspects": [{"name": "краткое название аспекта", "meaning": "string 40-50 слов"}],\n'
    '  "tips": [{"area": "сфера (1-2 слова)", "tip": "string 25-35 слов"}]\n'
    '}\n'
    'aspects: топ-3 ключевых аспекта из карты. tips: ровно 3 элемента (работа, отношения, рост).'
)

_PREMIUM_NATAL_REQUIRED_KEYS = frozenset({
    "overview", "sun_analysis", "moon_analysis", "rising_analysis",
    "career", "love", "finance", "health", "growth",
    "strengths", "challenges", "aspects", "tips",
})


async def interpret_natal_premium_async(
    *,
    sun_sign: str,
    moon_sign: str,
    rising_sign: str,
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
) -> dict[str, Any] | None:
    """Generate premium natal chart report via OpenRouter Gemini.

    Returns a validated dict with 13 keys matching _PREMIUM_NATAL_REQUIRED_KEYS,
    or None if the API call fails or returns an incomplete response.
    """
    safe_summary = _sanitize_user_input(natal_summary, max_length=600) if natal_summary else ""

    natal_block = (
        f"Солнце: {sun_sign}\n"
        f"Луна: {moon_sign}\n"
        f"Асцендент: {rising_sign}\n\n"
        f"Краткий контекст карты: {safe_summary or 'Нет данных'}\n\n"
        "Ключевые аспекты:\n"
        f"{chr(10).join(key_aspects[:6]) if key_aspects else 'Нет данных'}\n\n"
        "Планетный профиль:\n"
        f"{chr(10).join(planetary_profile[:6]) if planetary_profile else 'Нет данных'}\n\n"
        "Планеты в домах:\n"
        f"{chr(10).join(planets_in_houses[:8]) if planets_in_houses else 'Нет данных'}\n\n"
        "MC: "
        f"{mc_line or 'Нет данных'}\n"
        "Лунные узлы: "
        f"{nodes_line or 'Нет данных'}\n\n"
        "Конфигурации: "
        f"{chr(10).join(configurations[:3]) if configurations else 'Нет данных'}"
    )

    user_prompt = f"{natal_block}\n\nВерни JSON строго по этой схеме (все значения на русском):\n{_PREMIUM_NATAL_SCHEMA}"

    result = await _request_openrouter_json_async(
        system_prompt=_PREMIUM_NATAL_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=2000,
        temperature=0.5,
    )

    if not result:
        return None

    if not _PREMIUM_NATAL_REQUIRED_KEYS.issubset(result.keys()):
        missing = _PREMIUM_NATAL_REQUIRED_KEYS - result.keys()
        logger.error("OpenRouter premium natal: missing keys %s", missing)
        return None

    # Ensure aspects and tips are non-empty lists
    if not isinstance(result.get("aspects"), list) or not result["aspects"]:
        logger.error("OpenRouter premium natal: aspects is empty or not a list")
        return None
    if not isinstance(result.get("tips"), list) or not result["tips"]:
        logger.error("OpenRouter premium natal: tips is empty or not a list")
        return None

    return result


_PREMIUM_NUMEROLOGY_SYSTEM_PROMPT = (
    "Ты профессиональный нумеролог с глубоким знанием Пифагорейской нумерологии. "
    "Давай глубокую персональную интерпретацию на русском языке. "
    "Отвечай ТОЛЬКО валидным JSON строго по заданной схеме. "
    "Без markdown, без пояснений вне JSON, без дополнительных ключей."
)

_PREMIUM_NUMEROLOGY_SCHEMA = (
    '{\n'
    '  "life_path_deep": "string 150-200 слов — глубокий анализ числа жизненного пути: суть, предназначение, ключевые уроки, кармические задачи",\n'
    '  "expression_deep": "string 100-130 слов — число выражения: таланты, профессиональный потенциал, путь реализации",\n'
    '  "soul_urge_deep": "string 100-130 слов — число души: истинные желания, внутренняя мотивация, что приносит настоящее удовлетворение",\n'
    '  "personality_deep": "string 80-100 слов — число личности: как вас воспринимают, стиль общения, имидж",\n'
    '  "birthday_deep": "string 70-90 слов — число дня рождения: особый дар, специфический талант",\n'
    '  "personal_year_deep": "string 100-120 слов — число личного года: тема цикла, на что делать упор, что отпустить",\n'
    '  "synthesis": "string 150-200 слов — как все числа взаимодействуют: общий нумерологический портрет и ключевая тема жизни",\n'
    '  "strengths": ["строка 5-8 слов", "строка", "строка", "строка", "строка"],\n'
    '  "challenges": ["строка 5-8 слов", "строка", "строка"],\n'
    '  "advice": [{"area": "сфера (1-2 слова)", "tip": "string 40-50 слов"}]\n'
    '}\n'
    'strengths: ровно 5 элементов. challenges: ровно 3 элемента. advice: ровно 4 элемента (карьера, отношения, финансы, духовный рост).'
)

_PREMIUM_NUMEROLOGY_REQUIRED_KEYS = frozenset({
    "life_path_deep", "expression_deep", "soul_urge_deep", "personality_deep",
    "birthday_deep", "personal_year_deep", "synthesis", "strengths", "challenges", "advice",
})


async def interpret_numerology_premium_async(
    *,
    full_name: str,
    birth_date: str,
    life_path: int,
    expression: int,
    soul_urge: int,
    personality: int,
    birthday: int,
    personal_year: int,
) -> dict[str, Any] | None:
    """Generate premium numerology report via OpenRouter Gemini.

    Returns a validated dict with 10 keys matching _PREMIUM_NUMEROLOGY_REQUIRED_KEYS,
    or None if the API call fails or returns an incomplete response.
    """
    safe_name = _sanitize_user_input(full_name, max_length=200)

    def _arch(n: int) -> str:
        return _NUMEROLOGY_ARCHETYPES.get(n, "")

    master_nums = [n for n in (life_path, expression, soul_urge, personality, birthday, personal_year)
                   if n in {11, 22, 33}]
    master_note = (
        f"МАСТЕР-ЧИСЛА в профиле: {', '.join(str(n) for n in master_nums)} — "
        "обязательно укажи их усиленный потенциал и повышенную ответственность.\n"
        if master_nums else ""
    )

    user_prompt = (
        f"Имя: {safe_name}\n"
        f"Дата рождения: {birth_date}\n\n"
        f"{master_note}"
        f"Число Жизненного Пути: {life_path} ({_arch(life_path)})\n"
        f"Число Выражения (Судьбы): {expression} ({_arch(expression)})\n"
        f"Число Души: {soul_urge} ({_arch(soul_urge)})\n"
        f"Число Личности: {personality} ({_arch(personality)})\n"
        f"Число Дня Рождения: {birthday} ({_arch(birthday)})\n"
        f"Число Личного Года: {personal_year} ({_arch(personal_year)})\n\n"
        f"Верни JSON строго по этой схеме (все значения на русском):\n{_PREMIUM_NUMEROLOGY_SCHEMA}"
    )

    result = await _request_openrouter_json_async(
        system_prompt=_PREMIUM_NUMEROLOGY_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=2200,
        temperature=0.55,
    )

    if not result:
        return None

    if not _PREMIUM_NUMEROLOGY_REQUIRED_KEYS.issubset(result.keys()):
        missing = _PREMIUM_NUMEROLOGY_REQUIRED_KEYS - result.keys()
        logger.error("OpenRouter premium numerology: missing keys %s", missing)
        return None

    if not isinstance(result.get("strengths"), list) or len(result["strengths"]) < 3:
        logger.error("OpenRouter premium numerology: strengths invalid")
        return None
    if not isinstance(result.get("challenges"), list) or not result["challenges"]:
        logger.error("OpenRouter premium numerology: challenges invalid")
        return None
    if not isinstance(result.get("advice"), list) or not result["advice"]:
        logger.error("OpenRouter premium numerology: advice invalid")
        return None

    return result


async def interpret_forecast_stories_async(
    *,
    sun_sign: str,
    moon_sign: str,
    rising_sign: str,
    energy_score: int,
    mood: str,
    focus: str,
    natal_summary: str,
    key_aspects: list[str],
    mbti_type: str | None = None,
) -> list[dict[str, str]] | None:
    compact = _free_basic_mode()
    safe_natal_summary = _sanitize_user_input(natal_summary, max_length=350 if compact else 800) if natal_summary else ""
    mbti_line = ""
    if mbti_type and mbti_type in _MBTI_ARCHETYPE_DESCRIPTIONS:
        mbti_line = (
            f"Архетип разума (MBTI): {mbti_type} — {_MBTI_ARCHETYPE_DESCRIPTIONS[mbti_type]}\n"
            f"{_MBTI_TONE_HINTS.get(mbti_type, '')}\n"
        )
    if compact:
        prompt = (
            "Собери базовые сторис на день. Только русский язык. Верни только JSON.\n"
            'Формат: {"slides":[{"title":"...","body":"1-2 коротких предложения","badge":"коротко","tip":"короткий шаг","avoid":"коротко","timing":"коротко","animation":"glow|pulse|float|orbit"}]}\n'
            "Сделай ровно 4 слайда: день, работа/деньги, отношения, самочувствие.\n"
            "Тон: практично и кратко, без мистификации.\n"
            "Каждый body до 180 символов.\n\n"
            f"{mbti_line}"
            f"Солнце: {sun_sign}; Луна: {moon_sign}; Асцендент: {rising_sign}\n"
            f"Энергия: {energy_score}/100; Режим: {mood}; Фокус: {focus}\n"
            f"Натальный контекст: {safe_natal_summary or 'Нет данных'}\n"
            f"Аспекты: {', '.join(key_aspects[:3]) if key_aspects else 'Нет данных'}"
        )
    else:
        prompt = (
            "Собери персональный сторис-пак на один день в стиле практичного гороскопа.\n"
            "Нужен только русский язык, без markdown.\n"
            "Тон: конкретно, применимо в течение дня, без воды.\n"
            "Не обещай 100% исходов и не используй мистические формулировки.\n\n"
            "Верни СТРОГО JSON-объект:\n"
            '{"slides": [{"title": "...", "body": "2-3 коротких предложения", "badge": "короткая метка", '
            '"tip": "практический шаг до конца дня", "avoid": "чего избегать сегодня", '
            '"timing": "лучшее окно по времени", "animation": "одно из: glow, pulse, float, orbit"}]}\n\n'
            "Сделай 4 слайда:\n"
            "1) Общая энергия и фокус дня.\n"
            "2) Работа/деньги.\n"
            "3) Общение/отношения.\n"
            "4) Самочувствие и восстановление.\n\n"
            f"{mbti_line}"
            f"Солнце: {sun_sign}\n"
            f"Луна: {moon_sign}\n"
            f"Асцендент: {rising_sign}\n"
            f"Энергия: {energy_score}/100\n"
            f"Режим дня: {mood}\n"
            f"Фокус дня: {focus}\n"
            f"Натальный контекст: {safe_natal_summary or 'Нет данных'}\n"
            "Ключевые аспекты:\n"
            f"{chr(10).join(key_aspects[:4]) if key_aspects else 'Нет данных'}"
        )

    raw = await _request_llm_text_async(
        prompt=prompt,
        temperature=0.55,
        max_tokens=_json_task_max_tokens(450, 420),
    )
    if not raw:
        return None

    payload = _extract_json_dict(raw)
    if not payload:
        return None

    slides = _normalize_story_slides(payload)
    if len(slides) < 3:
        return None
    return slides
