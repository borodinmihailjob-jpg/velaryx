import asyncio
import logging
import os

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
    if MINI_APP_PUBLIC_BASE_URL:
        return MINI_APP_PUBLIC_BASE_URL
    return f"https://t.me/{BOT_USERNAME}/{MINI_APP_NAME}"


def miniapp_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Войти в портал 🪞",
                    web_app=WebAppInfo(url=miniapp_base_link()),
                )
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
    if not BOT_USERNAME and not MINI_APP_PUBLIC_BASE_URL:
        await message.answer("Нужно задать BOT_USERNAME или MINI_APP_PUBLIC_BASE_URL в окружении.")
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
    if not BOT_USERNAME and not MINI_APP_PUBLIC_BASE_URL:
        await message.answer("Нужно задать BOT_USERNAME или MINI_APP_PUBLIC_BASE_URL в окружении.")
        return
    await message.answer(
        "Откройте Mini App по кнопке ниже.",
        reply_markup=miniapp_keyboard(),
    )


@dp.message(F.text)
async def fallback_handler(message: Message) -> None:
    await message.answer(
        "Для работы используйте Mini App.",
        reply_markup=miniapp_keyboard(),
    )


async def main() -> None:
    try:
        await bot.set_my_commands([BotCommand(command="start", description="Войти в портал")])
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Войти в портал 🪞",
                web_app=WebAppInfo(url=miniapp_base_link()),
            )
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to set Telegram menu/commands: %s", exc)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
