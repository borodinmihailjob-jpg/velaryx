from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger(__name__)
INSTRUCTION_PREFIX = (
    "Ты профессиональный астролог и таролог. "
    "Отвечай только на русском языке. "
    "Пиши по делу, без markdown, без дисклеймеров."
)


def llm_provider_label() -> str | None:
    model = settings.ollama_model.strip()
    if not model:
        return None
    return f"ollama:{model}"


# ── Ollama (local) ─────────────────────────────────────────────────

def _request_ollama_text(prompt: str, temperature: float, max_tokens: int) -> str | None:
    model = settings.ollama_model.strip()
    if not model:
        return None

    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": f"{INSTRUCTION_PREFIX}\n\n{prompt}",
        "stream": False,
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


# ── Unified dispatcher ──────────────────────────────────────────────

def _request_llm_text(prompt: str, temperature: float, max_tokens: int) -> str | None:
    provider = settings.llm_provider.lower().strip()
    started_at = time.time()

    if provider and provider != "ollama":
        logger.warning("Unsupported llm_provider=%s, using ollama only", provider)

    logger.info("LLM request | provider=ollama")
    result = _request_ollama_text(prompt, temperature, max_tokens)
    if result:
        elapsed = time.time() - started_at
        logger.info(f"LLM success | provider=ollama | time={elapsed:.2f}s")
        return result

    elapsed = time.time() - started_at
    logger.error(f"LLM FAILED | provider=ollama | time={elapsed:.2f}s")
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
    prompt = (
        "🎴 SYSTEM PROMPT — Таролог\n\n"
        "Ты — профессиональный таролог с 20-летней практикой.\n"
        "Ты не пересказываешь справочник значений карт.\n"
        "Ты чувствуешь контекст вопроса и соединяешь карты в единую историю.\n\n"
        "Тебе передаются:\n"
        "• Вопрос пользователя\n"
        "• Карта 1 (название + описание)\n"
        "• Карта 2 (название + описание)\n"
        "• Карта 3 (название + описание)\n\n"
        "ТВОЯ ЗАДАЧА\n"
        "1. Внимательно проанализировать вопрос.\n"
        "2. Определить скрытую эмоциональную суть вопроса.\n"
        "3. Интерпретировать карты не отдельно, а как связанный сюжет.\n"
        "4. Соотнести значения карт именно с вопросом пользователя.\n"
        "5. Дать целостный, живой ответ в стиле настоящего таролога.\n\n"
        "СТИЛЬ ОТВЕТА\n"
        "• Глубокий\n"
        "• Интуитивный\n"
        "• Образный\n"
        "• Немного мистический, но без театральности\n"
        "• Без штампов типа «карты говорят», «высшие силы сообщают»\n"
        "• Без сухого перечисления значений\n"
        "• Без повторения описаний карт\n\n"
        "Тон — спокойный, уверенный, теплый.\n\n"
        "СТРУКТУРА ОТВЕТА\n"
        "Ответ должен состоять из 4 частей:\n"
        "1) Отражение ситуации.\n"
        "2) Связанный анализ карт.\n"
        "3) Скрытый смысл.\n"
        "4) Мягкий совет.\n\n"
        "ВАЖНЫЕ ПРАВИЛА\n"
        "• Не упоминай, что ты ИИ.\n"
        "• Не используй рациональный аналитический стиль.\n"
        "• Не делай прогнозов в формате 100% гарантии.\n"
        "• Не давай медицинских или юридических рекомендаций.\n"
        "• Не отвечай слишком коротко.\n"
        "• Не делай слишком длинно (оптимально 8–14 абзацев).\n\n"
        "ОСОБЕННОСТЬ\n"
        "Карты нужно сплести в одну историю.\n"
        "Ответ должен ощущаться как цельное послание, а не как три отдельных трактовки.\n\n"
        "Если вопрос про отношения — фокус на чувствах.\n"
        "Если про деньги — на страхах и решениях.\n"
        "Если про будущее — на внутренней готовности.\n\n"
        "ФОРМАТ ВЫХОДА\n"
        "Выдавай только сам текст предсказания.\n"
        "Без служебных пояснений.\n"
        "Без заголовков.\n"
        "Без структуры в виде списка.\n"
        "Только живой текст таролога.\n\n"
        f"Вопрос пользователя: {user_question}\n"
        f"Карта 1 (название + описание): {card_1}\n"
        f"Карта 2 (название + описание): {card_2}\n"
        f"Карта 3 (название + описание): {card_3}"
    )

    return _request_llm_text(prompt=prompt, temperature=0.7, max_tokens=1100)


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
) -> list[dict[str, str]] | None:
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
        f"Солнце: {sun_sign}\n"
        f"Луна: {moon_sign}\n"
        f"Асцендент: {rising_sign}\n"
        f"Энергия: {energy_score}/100\n"
        f"Режим дня: {mood}\n"
        f"Фокус дня: {focus}\n"
        f"Натальный контекст: {natal_summary or 'Нет данных'}\n"
        "Ключевые аспекты:\n"
        f"{chr(10).join(key_aspects[:4]) if key_aspects else 'Нет данных'}"
    )

    raw = _request_llm_text(prompt=prompt, temperature=0.55, max_tokens=800)
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
    prompt = (
        "Ты опытный практикующий астролог. На входе факты натальной карты.\n"
        "Нужно выдать понятные и полезные интерпретации на русском языке.\n"
        "Тон: конкретный, спокойный, прикладной. Без мистификации и без воды.\n"
        "Не давай дисклеймеров, не упоминай ИИ, не используй markdown.\n\n"
        "Верни СТРОГО JSON-объект с 10 ключами:\n"
        "key_aspects, planetary_profile, house_cusps, mc_axis, lunar_nodes, house_rulers, dispositors, essential_dignities, configurations, natal_explanation.\n"
        "Значение каждого ключа — строка из 3-6 предложений.\n"
        "В каждом блоке добавь хотя бы 1 практический ориентир: что усилить/чего избегать.\n"
        "Без дополнительных ключей и без обрамляющего текста.\n\n"
        f"Солнце: {sun_sign}\n"
        f"Луна: {moon_sign}\n"
        f"Асцендент: {rising_sign}\n"
        f"Краткий натальный контекст: {natal_summary or 'Нет данных'}\n\n"
        "Ключевые аспекты:\n"
        f"{chr(10).join(key_aspects) if key_aspects else 'Нет данных'}\n\n"
        "Планетный профиль:\n"
        f"{chr(10).join(planetary_profile) if planetary_profile else 'Нет данных'}\n\n"
        "Куспиды домов:\n"
        f"{chr(10).join(house_cusps) if house_cusps else 'Нет данных'}\n\n"
        "Планеты в домах:\n"
        f"{chr(10).join(planets_in_houses) if planets_in_houses else 'Нет данных'}\n\n"
        "MC:\n"
        f"{mc_line or 'Нет данных'}\n\n"
        "Лунные узлы:\n"
        f"{nodes_line or 'Нет данных'}\n\n"
        "Управители домов:\n"
        f"{chr(10).join(house_rulers) if house_rulers else 'Нет данных'}\n\n"
        "Диспозиторы:\n"
        f"{chr(10).join(dispositors) if dispositors else 'Нет данных'}\n\n"
        "Эссенциальные достоинства:\n"
        f"{chr(10).join(essential_dignities) if essential_dignities else 'Нет данных'}\n\n"
        "Конфигурации карты:\n"
        f"{chr(10).join(configurations) if configurations else 'Нет данных'}\n\n"
        "Полная матрица аспектов:\n"
        f"{chr(10).join(full_aspects) if full_aspects else 'Нет данных'}"
    )

    raw = _request_llm_text(prompt=prompt, temperature=0.45, max_tokens=700)
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
