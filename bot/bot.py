import asyncio
import os

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
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


async def create_invite_token(tg_user_id: int) -> str:
    headers = {"X-TG-USER-ID": str(tg_user_id)}
    if INTERNAL_API_KEY:
        headers["X-Internal-API-Key"] = INTERNAL_API_KEY

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{API_BASE_URL}/v1/compat/invites",
            headers=headers,
            json={"ttl_days": 7, "max_uses": 1},
        )
        response.raise_for_status()
    return response.json()["token"]


def miniapp_base_link() -> str:
    return f"https://t.me/{BOT_USERNAME}/{MINI_APP_NAME}"


def miniapp_link(token: str) -> str:
    return f"https://t.me/{BOT_USERNAME}/{MINI_APP_NAME}?startapp={token}"


async def fetch_daily_forecast(tg_user_id: int) -> dict:
    headers = {"X-TG-USER-ID": str(tg_user_id)}
    if INTERNAL_API_KEY:
        headers["X-Internal-API-Key"] = INTERNAL_API_KEY

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{API_BASE_URL}/v1/forecast/daily",
            headers=headers,
        )
        response.raise_for_status()
        return response.json()


async def draw_tarot_for_user(tg_user_id: int, question: str | None) -> dict:
    headers = {"X-TG-USER-ID": str(tg_user_id)}
    if INTERNAL_API_KEY:
        headers["X-Internal-API-Key"] = INTERNAL_API_KEY

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"{API_BASE_URL}/v1/tarot/draw",
            headers=headers,
            json={"spread_type": "three_card", "question": question},
        )
        response.raise_for_status()
        return response.json()


@dp.message(Command("start"))
async def start_handler(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/app - открыть Mini App\n"
        "/natal - инструкция по натальной карте\n"
        "/daily - ежедневный прогноз\n"
        "/tarot [вопрос] - расклад 3 карты\n"
        "/compat - ссылка совместимости"
    )


@dp.message(Command("app"))
async def app_handler(message: Message) -> None:
    if not BOT_USERNAME:
        await message.answer("Нужно задать BOT_USERNAME в окружении.")
        return
    await message.answer(f"Mini App: {miniapp_base_link()}")


@dp.message(Command("natal"))
async def natal_handler(message: Message) -> None:
    await message.answer(
        "Заполните birth-профиль в Mini App: дата, время, место, координаты и timezone.\n"
        f"Открыть: {miniapp_base_link()}"
    )


@dp.message(Command("daily"))
async def daily_handler(message: Message) -> None:
    if not message.from_user:
        await message.answer("Не удалось определить пользователя Telegram.")
        return

    try:
        forecast = await fetch_daily_forecast(message.from_user.id)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            await message.answer("Сначала создайте и рассчитайте натальную карту в Mini App.")
            return
        await message.answer("Не удалось получить прогноз. Попробуйте позже.")
        return
    except Exception:
        await message.answer("Не удалось получить прогноз. Попробуйте позже.")
        return

    await message.answer(
        f"Прогноз на {forecast['date']}\n"
        f"Энергия: {forecast['energy_score']}/100\n"
        f"{forecast['summary']}"
    )


@dp.message(Command("tarot"))
async def tarot_handler(message: Message) -> None:
    if not message.from_user:
        await message.answer("Не удалось определить пользователя Telegram.")
        return

    question = None
    if message.text and len(message.text.split(maxsplit=1)) > 1:
        question = message.text.split(maxsplit=1)[1]

    try:
        reading = await draw_tarot_for_user(message.from_user.id, question)
    except Exception:
        await message.answer("Не удалось сделать расклад. Попробуйте позже.")
        return

    lines = [f"Таро ({reading['spread_type']}):"]
    for card in reading["cards"]:
        orientation = "перевернута" if card["is_reversed"] else "прямая"
        lines.append(f"{card['position']}. {card['card_name']} ({orientation}) - {card['meaning']}")

    await message.answer("\n".join(lines))


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
