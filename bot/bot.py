import asyncio
import os
from datetime import datetime, timezone

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
MINI_APP_NAME = os.getenv("MINI_APP_NAME", "app")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")

API_BASE_URL = os.getenv("API_BASE_URL")
if not API_BASE_URL:
    api_host = os.getenv("API_HOST", "localhost")
    api_port = os.getenv("API_PORT", "8000")
    API_BASE_URL = f"http://{api_host}:{api_port}"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def _headers(tg_user_id: int) -> dict[str, str]:
    headers = {"X-TG-USER-ID": str(tg_user_id)}
    if INTERNAL_API_KEY:
        headers["X-Internal-API-Key"] = INTERNAL_API_KEY
    return headers


def _command_arg(text: str | None) -> str | None:
    if not text:
        return None
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None
    arg = parts[1].strip()
    return arg or None


def miniapp_base_link() -> str:
    return f"https://t.me/{BOT_USERNAME}/{MINI_APP_NAME}"


def miniapp_link(token: str) -> str:
    return f"https://t.me/{BOT_USERNAME}/{MINI_APP_NAME}?startapp={token}"


def miniapp_screen_link(screen_code: str) -> str:
    return miniapp_link(f"sc_{screen_code}")


async def create_invite_token(tg_user_id: int) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{API_BASE_URL}/v1/compat/invites",
            headers=_headers(tg_user_id),
            json={"ttl_days": 7, "max_uses": 1},
        )
        response.raise_for_status()
    return response.json()["token"]


async def fetch_daily_forecast(tg_user_id: int) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{API_BASE_URL}/v1/forecast/daily",
            headers=_headers(tg_user_id),
        )
        response.raise_for_status()
        return response.json()


async def fetch_natal_full(tg_user_id: int) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{API_BASE_URL}/v1/natal/full",
            headers=_headers(tg_user_id),
        )
        response.raise_for_status()
        return response.json()


async def fetch_combo_insight(tg_user_id: int, question: str | None) -> dict:
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.post(
            f"{API_BASE_URL}/v1/insights/astro-tarot",
            headers=_headers(tg_user_id),
            json={"question": question, "spread_type": "three_card"},
        )
        response.raise_for_status()
        return response.json()


async def draw_tarot_for_user(tg_user_id: int, question: str | None) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{API_BASE_URL}/v1/tarot/draw",
            headers=_headers(tg_user_id),
            json={"spread_type": "three_card", "question": question},
        )
        response.raise_for_status()
        return response.json()


async def fetch_natal_pdf(tg_user_id: int) -> bytes:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{API_BASE_URL}/v1/reports/natal.pdf",
            headers=_headers(tg_user_id),
        )
        response.raise_for_status()
        return response.content


@dp.message(Command("start"))
async def start_handler(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/app - открыть Mini App\n"
        "/natal - полная натальная карта\n"
        "/daily - ежедневный прогноз\n"
        "/tarot [вопрос] - расклад 3 карты\n"
        "/combo [вопрос] - астрология + таро\n"
        "/compat - ссылка совместимости\n"
        "/report - скачать PDF-отчет"
    )


@dp.message(Command("app"))
async def app_handler(message: Message) -> None:
    if not BOT_USERNAME:
        await message.answer("Нужно задать BOT_USERNAME в окружении.")
        return
    await message.answer(f"Mini App: {miniapp_base_link()}")


@dp.message(Command("natal"))
async def natal_handler(message: Message) -> None:
    if not BOT_USERNAME:
        await message.answer("Нужно задать BOT_USERNAME в окружении.")
        return
    if not message.from_user:
        await message.answer("Не удалось определить пользователя Telegram.")
        return

    try:
        natal = await fetch_natal_full(message.from_user.id)
        sections = natal.get("interpretation_sections") or []
        summary = sections[0]["text"] if sections else "Откройте Mini App для полного разбора."
        await message.answer(
            f"Натальная карта: {natal.get('sun_sign')} / {natal.get('moon_sign')} / {natal.get('rising_sign')}\n"
            f"{summary}\n\n"
            f"Полный экран: {miniapp_screen_link('natal')}"
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            await message.answer(
                "Сначала заполните данные рождения в Mini App.\n"
                f"Открыть: {miniapp_screen_link('onboarding')}"
            )
            return
        await message.answer("Не удалось получить натальную карту. Попробуйте позже.")
    except Exception:
        await message.answer("Не удалось получить натальную карту. Попробуйте позже.")


@dp.message(Command("daily"))
async def daily_handler(message: Message) -> None:
    if not message.from_user:
        await message.answer("Не удалось определить пользователя Telegram.")
        return

    try:
        forecast = await fetch_daily_forecast(message.from_user.id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            await message.answer(
                "Сначала создайте и рассчитайте натальную карту в Mini App.\n"
                f"Открыть: {miniapp_screen_link('onboarding')}"
            )
            return
        await message.answer("Не удалось получить прогноз. Попробуйте позже.")
        return
    except Exception:
        await message.answer("Не удалось получить прогноз. Попробуйте позже.")
        return

    await message.answer(
        f"Прогноз на {forecast['date']}\n"
        f"Энергия: {forecast['energy_score']}/100\n"
        f"{forecast['summary']}\n\n"
        f"Сторис-режим: {miniapp_screen_link('stories')}"
    )


@dp.message(Command("tarot"))
async def tarot_handler(message: Message) -> None:
    if not message.from_user:
        await message.answer("Не удалось определить пользователя Telegram.")
        return

    question = _command_arg(message.text)

    try:
        reading = await draw_tarot_for_user(message.from_user.id, question)
    except Exception:
        await message.answer("Не удалось сделать расклад. Попробуйте позже.")
        return

    lines = [f"Таро ({reading['spread_type']}):"]
    for card in reading["cards"]:
        orientation = "перевернутая" if card["is_reversed"] else "прямая"
        lines.append(f"{card['position']}. {card['card_name']} ({orientation})")

    ai_text = reading.get("ai_interpretation")
    if ai_text:
        lines.append("")
        lines.append(ai_text)

    lines.append(f"\nПолная версия: {miniapp_screen_link('tarot')}")
    await message.answer("\n".join(lines))


@dp.message(Command("combo"))
async def combo_handler(message: Message) -> None:
    if not message.from_user:
        await message.answer("Не удалось определить пользователя Telegram.")
        return

    question = _command_arg(message.text)
    try:
        insight = await fetch_combo_insight(message.from_user.id, question)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            await message.answer(
                "Для комбинированного сценария сначала нужна натальная карта.\n"
                f"Открыть: {miniapp_screen_link('onboarding')}"
            )
            return
        await message.answer("Не удалось сделать комбинированный разбор. Попробуйте позже.")
        return
    except Exception:
        await message.answer("Не удалось сделать комбинированный разбор. Попробуйте позже.")
        return

    card_name = ""
    cards = insight.get("tarot_cards") or []
    if cards:
        card_name = cards[0].get("card_name", "")

    await message.answer(
        "Комбо: астрология + таро\n"
        f"{insight.get('combined_advice', '')}\n"
        f"Источник: {insight.get('llm_provider') or 'локальная логика'}\n"
        f"Карта-фокус: {card_name or '—'}\n\n"
        f"Открыть в Mini App: {miniapp_screen_link('combo')}"
    )


@dp.message(Command("report"))
async def report_handler(message: Message) -> None:
    if not message.from_user:
        await message.answer("Не удалось определить пользователя Telegram.")
        return

    try:
        pdf_bytes = await fetch_natal_pdf(message.from_user.id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            await message.answer(
                "Сначала создайте натальную карту, затем сформируем PDF.\n"
                f"Открыть: {miniapp_screen_link('onboarding')}"
            )
            return
        await message.answer("Не удалось сформировать PDF-отчет. Попробуйте позже.")
        return
    except Exception:
        await message.answer("Не удалось сформировать PDF-отчет. Попробуйте позже.")
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    filename = f"natal-report-{timestamp}.pdf"
    await message.answer_document(
        BufferedInputFile(pdf_bytes, filename=filename),
        caption="Ваш PDF-отчет по натальной карте",
    )


@dp.message(Command("compat"))
async def compat_handler(message: Message) -> None:
    if not BOT_USERNAME:
        await message.answer("Нужно задать BOT_USERNAME в окружении.")
        return
    if not message.from_user:
        await message.answer("Не удалось определить пользователя Telegram.")
        return

    try:
        token = await create_invite_token(message.from_user.id)
    except Exception:
        await message.answer("Не удалось создать ссылку совместимости. Попробуйте позже.")
        return

    await message.answer(
        "Поделитесь ссылкой и узнайте совместимость:\n"
        f"{miniapp_link(token)}"
    )


@dp.message(F.text)
async def fallback_handler(message: Message) -> None:
    await message.answer("Используйте /start для списка команд")


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
