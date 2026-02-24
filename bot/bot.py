import asyncio
import logging
import os
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, Message, WebAppInfo
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
MINI_APP_NAME = os.getenv("MINI_APP_NAME", "app")
MINI_APP_PUBLIC_BASE_URL = os.getenv("MINI_APP_PUBLIC_BASE_URL", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")

logger = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def miniapp_base_link() -> str:
    if BOT_USERNAME:
        return f"https://t.me/{BOT_USERNAME}/{MINI_APP_NAME}"
    return ""


def miniapp_webapp_url() -> str | None:
    if MINI_APP_PUBLIC_BASE_URL:
        candidate = MINI_APP_PUBLIC_BASE_URL.rstrip("/")
        parsed = urlparse(candidate)
        hostname = (parsed.hostname or "").lower()
        is_tg_link = hostname in {"t.me", "telegram.me", "www.t.me", "www.telegram.me"}
        if parsed.scheme == "https" and parsed.netloc and not is_tg_link:
            return candidate
    return None


def has_miniapp_link() -> bool:
    return bool(miniapp_webapp_url() or miniapp_base_link())


def miniapp_keyboard() -> InlineKeyboardMarkup:
    webapp_url = miniapp_webapp_url()
    if webapp_url:
        button = InlineKeyboardButton(
            text="Войти в портал 🪞",
            web_app=WebAppInfo(url=webapp_url),
        )
    else:
        deep_link = miniapp_base_link()
        if not deep_link:
            raise RuntimeError("BOT_USERNAME or valid MINI_APP_PUBLIC_BASE_URL is required")
        button = InlineKeyboardButton(
            text="Войти в портал 🪞",
            url=deep_link,
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button
            ]
        ]
    )


@dp.message(Command("start"))
async def start_handler(message: Message) -> None:
    logger.info(
        "Запуск бота пользователем | tg_user_id=%s | username=%s",
        message.from_user.id if message.from_user else "-",
        message.from_user.username if message.from_user else "-",
    )
    if not has_miniapp_link():
        await message.answer("Нужно задать BOT_USERNAME или корректный MINI_APP_PUBLIC_BASE_URL (https://...).")
        return
    await message.answer(
        "Символы уже приходят в движение…🕯\n"
        "Твой вопрос будет услышан, и нити судьбы сплетутся в историю 🔮✨\n\n"
        "✨ Коснись портала ниже —\n"
        "и позволь раскладу открыться 🃏",
        reply_markup=miniapp_keyboard(),
    )


@dp.message(Command("app"))
async def app_handler(message: Message) -> None:
    logger.info(
        "Команда /app | tg_user_id=%s",
        message.from_user.id if message.from_user else "-",
    )
    if not has_miniapp_link():
        await message.answer("Нужно задать BOT_USERNAME или корректный MINI_APP_PUBLIC_BASE_URL (https://...).")
        return
    await message.answer(
        "Откройте Mini App по кнопке ниже.",
        reply_markup=miniapp_keyboard(),
    )


@dp.message(F.text)
async def fallback_handler(message: Message) -> None:
    if not has_miniapp_link():
        await message.answer("Нужно задать BOT_USERNAME или корректный MINI_APP_PUBLIC_BASE_URL (https://...).")
        return
    await message.answer(
        "Для работы используйте Mini App.",
        reply_markup=miniapp_keyboard(),
    )


async def main() -> None:
    try:
        await bot.set_my_commands([BotCommand(command="start", description="Войти в портал")])
        webapp_url = miniapp_webapp_url()
        if webapp_url:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Войти в портал 🪞",
                    web_app=WebAppInfo(url=webapp_url),
                )
            )
        elif MINI_APP_PUBLIC_BASE_URL:
            logger.warning(
                "MINI_APP_PUBLIC_BASE_URL must be a direct HTTPS Mini App URL (not t.me). "
                "Menu WebApp button was not configured; /start will use a regular deep link."
            )
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to set Telegram menu/commands: %s", exc)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
