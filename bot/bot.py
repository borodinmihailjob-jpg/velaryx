import asyncio
import logging
import os
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    PreCheckoutQuery,
    WebAppInfo,
)
from dotenv import load_dotenv
import httpx

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
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "").strip()
INTERNAL_API_BASE_URL = os.getenv("INTERNAL_API_BASE_URL", "http://api:8000").strip().rstrip("/")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")

logger = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


BOT_COPY = {
    "ru": {
        "portal_btn": "Войти в портал 🪞",
        "start_text": (
            "Символы уже приходят в движение…🕯\n"
            "Твой вопрос будет услышан, и нити судьбы сплетутся в историю 🔮✨\n\n"
            "✨ Коснись портала ниже —\n"
            "и позволь раскладу открыться 🃏"
        ),
        "app_text": "Откройте Mini App по кнопке ниже.",
        "fallback_text": "Для работы используйте Mini App.",
        "link_error": "Нужно задать BOT_USERNAME или корректный MINI_APP_PUBLIC_BASE_URL (https://...).",
    },
    "en": {
        "portal_btn": "Open portal 🪞",
        "start_text": (
            "The symbols are already moving…🕯\n"
            "Your question will be heard, and the threads of fate will weave into a story 🔮✨\n\n"
            "✨ Tap the portal below —\n"
            "and let the spread reveal itself 🃏"
        ),
        "app_text": "Open the Mini App using the button below.",
        "fallback_text": "Use the Mini App to continue.",
        "link_error": "Set BOT_USERNAME or a valid MINI_APP_PUBLIC_BASE_URL (https://...).",
    },
}


def normalize_lang_code(raw: str | None) -> str:
    if not raw:
        return "ru"
    source = str(raw).strip().lower().replace("_", "-")
    if not source:
        return "ru"
    base = source.split("-", 1)[0]
    return "ru" if base == "ru" else "en"


def copy_for_lang(raw: str | None) -> dict[str, str]:
    return BOT_COPY[normalize_lang_code(raw)]


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


def miniapp_keyboard(language_code: str | None = None) -> InlineKeyboardMarkup:
    copy = copy_for_lang(language_code)
    webapp_url = miniapp_webapp_url()
    if webapp_url:
        button = InlineKeyboardButton(
            text=copy["portal_btn"],
            web_app=WebAppInfo(url=webapp_url),
        )
    else:
        deep_link = miniapp_base_link()
        if not deep_link:
            raise RuntimeError("BOT_USERNAME or valid MINI_APP_PUBLIC_BASE_URL is required")
        button = InlineKeyboardButton(
            text=copy["portal_btn"],
            url=deep_link,
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                button
            ]
        ]
    )


async def sync_user_profile_from_start(message: Message) -> None:
    user = message.from_user
    if user is None:
        return
    if not INTERNAL_API_KEY or not INTERNAL_API_BASE_URL:
        return

    payload = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "language_code": user.language_code,
        "is_premium": user.is_premium,
        "allows_write_to_pm": getattr(user, "allows_write_to_pm", None),
    }
    headers = {
        "X-Internal-API-Key": INTERNAL_API_KEY,
        "X-TG-User-ID": str(user.id),
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(f"{INTERNAL_API_BASE_URL}/v1/users/me", headers=headers, json=payload)
            response.raise_for_status()
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to sync user language on /start | tg_user_id=%s | err=%s", user.id, exc)


async def validate_payment_for_pre_checkout(invoice_payload: str, tg_user_id: int | None) -> bool:
    """Returns True if payment should be approved. Fails open on backend errors."""
    if not INTERNAL_API_KEY or not INTERNAL_API_BASE_URL:
        return True
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(
                f"{INTERNAL_API_BASE_URL}/v1/payments/internal/validate-invoice",
                headers={"X-Internal-API-Key": INTERNAL_API_KEY},
                json={"invoice_payload": invoice_payload, "tg_user_id": tg_user_id},
            )
            if response.status_code == 200:
                return bool(response.json().get("ok", True))
    except Exception as exc:
        logger.warning("Pre-checkout validation failed (approving anyway): %s", exc)
    return True  # fail open: never reject a valid payment due to backend unavailability


async def notify_backend_about_successful_payment(message: Message) -> None:
    payment = message.successful_payment
    if payment is None:
        return
    if not INTERNAL_API_KEY or not INTERNAL_API_BASE_URL:
        logger.warning("Skipping payment sync: INTERNAL_API_KEY or INTERNAL_API_BASE_URL not configured")
        return

    payload = {
        "invoice_payload": payment.invoice_payload,
        "tg_user_id": message.from_user.id if message.from_user else None,
        "currency": payment.currency,
        "total_amount": payment.total_amount,
        "telegram_payment_charge_id": payment.telegram_payment_charge_id,
        "provider_payment_charge_id": payment.provider_payment_charge_id,
    }
    headers = {
        "X-Internal-API-Key": INTERNAL_API_KEY,
    }

    max_retries = 4
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{INTERNAL_API_BASE_URL}/v1/payments/internal/telegram-success",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
            logger.info(
                "Payment sync OK | attempt=%d | tg_user_id=%s | invoice_payload=%s",
                attempt + 1,
                message.from_user.id if message.from_user else "-",
                payment.invoice_payload,
            )
            return  # success — stop retrying
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            if attempt < max_retries - 1:
                wait_seconds = 2 ** attempt  # 1 s, 2 s, 4 s
                logger.warning(
                    "Payment sync failed (attempt %d/%d), retry in %ds | err=%s",
                    attempt + 1, max_retries, wait_seconds, exc,
                )
                await asyncio.sleep(wait_seconds)

    logger.error(  # pragma: no cover
        "CRITICAL: payment sync FAILED after %d attempts — manual recovery needed! "
        "tg_user_id=%s | invoice_payload=%s | charge_id=%s | err=%s",
        max_retries,
        message.from_user.id if message.from_user else "-",
        payment.invoice_payload,
        payment.telegram_payment_charge_id,
        last_exc,
    )


@dp.message(Command("start"))
async def start_handler(message: Message) -> None:
    user_lang = message.from_user.language_code if message.from_user else None
    copy = copy_for_lang(user_lang)
    logger.info(
        "Запуск бота пользователем | tg_user_id=%s | username=%s | language_code=%s",
        message.from_user.id if message.from_user else "-",
        message.from_user.username if message.from_user else "-",
        user_lang or "-",
    )
    await sync_user_profile_from_start(message)
    if not has_miniapp_link():
        await message.answer(copy["link_error"])
        return
    await message.answer(
        copy["start_text"],
        reply_markup=miniapp_keyboard(user_lang),
    )


@dp.message(Command("app"))
async def app_handler(message: Message) -> None:
    user_lang = message.from_user.language_code if message.from_user else None
    copy = copy_for_lang(user_lang)
    logger.info(
        "Команда /app | tg_user_id=%s",
        message.from_user.id if message.from_user else "-",
    )
    if not has_miniapp_link():
        await message.answer(copy["link_error"])
        return
    await message.answer(
        copy["app_text"],
        reply_markup=miniapp_keyboard(user_lang),
    )


@dp.pre_checkout_query()
async def pre_checkout_handler(query: PreCheckoutQuery) -> None:
    tg_user_id = query.from_user.id if query.from_user else None
    should_approve = await validate_payment_for_pre_checkout(query.invoice_payload, tg_user_id)
    if should_approve:
        await bot.answer_pre_checkout_query(query.id, ok=True)
    else:
        await bot.answer_pre_checkout_query(
            query.id,
            ok=False,
            error_message="Этот счёт уже был оплачен. Пожалуйста, вернитесь в приложение.",
        )


@dp.message(F.successful_payment)
async def successful_payment_handler(message: Message) -> None:
    payment = message.successful_payment
    if payment is None:
        return
    logger.info(
        "Successful payment | tg_user_id=%s | currency=%s | total=%s | payload=%s",
        message.from_user.id if message.from_user else "-",
        payment.currency,
        payment.total_amount,
        payment.invoice_payload,
    )
    await notify_backend_about_successful_payment(message)
    if has_miniapp_link():
        invoice_payload = payment.invoice_payload or ""
        is_wallet_topup = str(invoice_payload).startswith("stars:wallet_topup_")
        if is_wallet_topup:
            await message.answer("Баланс пополнен ✨ Возвращайтесь в Mini App — звёзды уже зачислены.")
        else:
            await message.answer("Оплата получена. Возвращайтесь в Mini App — отчёт готов к запуску.")


@dp.message(F.text)
async def fallback_handler(message: Message) -> None:
    user_lang = message.from_user.language_code if message.from_user else None
    copy = copy_for_lang(user_lang)
    if not has_miniapp_link():
        await message.answer(copy["link_error"])
        return
    await message.answer(
        copy["fallback_text"],
        reply_markup=miniapp_keyboard(user_lang),
    )


async def main() -> None:
    try:
        await bot.set_my_commands([BotCommand(command="start", description="Войти в портал")])
        webapp_url = miniapp_webapp_url()
        if webapp_url:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text=BOT_COPY["ru"]["portal_btn"],
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
