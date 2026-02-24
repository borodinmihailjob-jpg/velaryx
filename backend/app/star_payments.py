import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models
from .config import settings

logger = logging.getLogger("astrobot.star_payments")

STARS_CURRENCY = "XTR"
PAYMENT_STATUS_CREATED = "created"
PAYMENT_STATUS_INVOICED = "invoiced"
PAYMENT_STATUS_PAID = "paid"
PAYMENT_STATUS_CONSUMED = "consumed"
PAYMENT_STATUS_FAILED = "failed"
PAYMENT_STATUS_CANCELLED = "cancelled"


@dataclass(frozen=True)
class StarProduct:
    feature: str
    amount_stars: int
    title: str
    description: str


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _product_catalog() -> dict[str, StarProduct]:
    return {
        "natal_premium": StarProduct(
            feature="natal_premium",
            amount_stars=max(1, int(settings.stars_price_natal_premium)),
            title="Детальный натальный отчёт",
            description="Персональный астрологический отчёт Gemini",
        ),
        "tarot_premium": StarProduct(
            feature="tarot_premium",
            amount_stars=max(1, int(settings.stars_price_tarot_premium)),
            title="Глубокий расклад Таро",
            description="Расклад Таро с детальной интерпретацией Gemini",
        ),
        "numerology_premium": StarProduct(
            feature="numerology_premium",
            amount_stars=max(1, int(settings.stars_price_numerology_premium)),
            title="Глубокий нумерологический отчёт",
            description="Подробный нумерологический анализ Gemini",
        ),
    }


def get_product(feature: str) -> StarProduct:
    product = _product_catalog().get(feature)
    if product is None:
        raise HTTPException(status_code=400, detail="Неизвестный платный продукт")
    return product


def list_products() -> list[StarProduct]:
    return list(_product_catalog().values())


def _telegram_api_url(method: str) -> str:
    if not settings.bot_token:
        raise HTTPException(status_code=503, detail="BOT_TOKEN не настроен")
    return f"https://api.telegram.org/bot{settings.bot_token}/{method}"


async def _create_telegram_invoice_link(*, product: StarProduct, invoice_payload: str) -> str:
    body = {
        "title": product.title,
        "description": product.description,
        "payload": invoice_payload,
        "currency": STARS_CURRENCY,
        "prices": [{"label": product.title, "amount": product.amount_stars}],
    }
    try:
        async with httpx.AsyncClient(timeout=settings.telegram_bot_api_timeout_seconds) as client:
            response = await client.post(_telegram_api_url("createInvoiceLink"), json=body)
        response.raise_for_status()
        payload = response.json()
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Telegram createInvoiceLink failed: %s", exc)
        raise HTTPException(status_code=502, detail="Не удалось создать счёт Telegram Stars")

    if not payload.get("ok") or not isinstance(payload.get("result"), str):
        logger.warning("Telegram createInvoiceLink error response: %s", payload)
        raise HTTPException(status_code=502, detail="Telegram не принял запрос на оплату")
    return payload["result"]


def _payment_error_for_status(status: str) -> HTTPException:
    if status in {PAYMENT_STATUS_CREATED, PAYMENT_STATUS_INVOICED}:
        return HTTPException(status_code=409, detail="Оплата ещё не подтверждена Telegram")
    if status == PAYMENT_STATUS_CONSUMED:
        return HTTPException(status_code=409, detail="Платёж уже использован")
    if status in {PAYMENT_STATUS_FAILED, PAYMENT_STATUS_CANCELLED}:
        return HTTPException(status_code=402, detail="Оплата не завершена")
    return HTTPException(status_code=402, detail="Требуется оплата Stars")


async def create_invoice_for_user(
    db: Session,
    *,
    user: models.User,
    feature: str,
    meta_payload: dict | None = None,
) -> models.StarPayment:
    product = get_product(feature)
    invoice_payload = f"stars:{feature}:{user.tg_user_id}:{uuid.uuid4().hex}"
    now = utcnow()
    payment = models.StarPayment(
        user_id=user.id,
        tg_user_id=user.tg_user_id,
        feature=product.feature,
        amount_stars=product.amount_stars,
        currency=STARS_CURRENCY,
        status=PAYMENT_STATUS_CREATED,
        invoice_payload=invoice_payload,
        meta_payload=meta_payload,
        created_at=now,
        updated_at=now,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    try:
        invoice_link = await _create_telegram_invoice_link(product=product, invoice_payload=invoice_payload)
    except HTTPException:
        payment.status = PAYMENT_STATUS_FAILED
        payment.updated_at = utcnow()
        db.add(payment)
        db.commit()
        db.refresh(payment)
        raise

    payment.invoice_link = invoice_link
    payment.status = PAYMENT_STATUS_INVOICED
    payment.updated_at = utcnow()
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def get_user_payment(db: Session, *, user: models.User, payment_id: uuid.UUID) -> models.StarPayment:
    payment = (
        db.query(models.StarPayment)
        .filter(models.StarPayment.id == payment_id, models.StarPayment.user_id == user.id)
        .first()
    )
    if payment is None:
        raise HTTPException(status_code=404, detail="Платёж не найден")
    return payment


def mark_payment_paid_from_telegram(
    db: Session,
    *,
    invoice_payload: str,
    tg_user_id: int | None,
    currency: str,
    total_amount: int,
    telegram_payment_charge_id: str | None,
    provider_payment_charge_id: str | None,
) -> models.StarPayment:
    payment = db.query(models.StarPayment).filter(models.StarPayment.invoice_payload == invoice_payload).first()
    if payment is None:
        raise HTTPException(status_code=404, detail="Платёж по invoice_payload не найден")

    if tg_user_id is not None and int(payment.tg_user_id) != int(tg_user_id):
        raise HTTPException(status_code=409, detail="Пользователь платежа не совпадает")
    if str(currency).upper() != str(payment.currency).upper():
        raise HTTPException(status_code=409, detail="Валюта платежа не совпадает")
    if int(total_amount) != int(payment.amount_stars):
        raise HTTPException(status_code=409, detail="Сумма платежа не совпадает")

    if telegram_payment_charge_id and payment.telegram_payment_charge_id not in (None, telegram_payment_charge_id):
        raise HTTPException(status_code=409, detail="Платёж уже подтверждён другим charge_id")

    # Idempotent: keep consumed status if report was already started.
    if payment.status not in {PAYMENT_STATUS_PAID, PAYMENT_STATUS_CONSUMED}:
        payment.status = PAYMENT_STATUS_PAID
        payment.paid_at = payment.paid_at or utcnow()

    payment.telegram_payment_charge_id = telegram_payment_charge_id or payment.telegram_payment_charge_id
    payment.provider_payment_charge_id = provider_payment_charge_id or payment.provider_payment_charge_id
    payment.updated_at = utcnow()
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def claim_paid_payment_for_feature(
    db: Session,
    *,
    user: models.User,
    feature: str,
    payment_id: uuid.UUID | None,
) -> models.StarPayment:
    if payment_id is None:
        raise HTTPException(status_code=402, detail="Для премиум-отчёта нужна оплата Stars")

    payment = get_user_payment(db, user=user, payment_id=payment_id)
    if payment.feature != feature:
        raise HTTPException(status_code=409, detail="Платёж относится к другому типу отчёта")
    if payment.status != PAYMENT_STATUS_PAID:
        raise _payment_error_for_status(payment.status)

    now = utcnow()
    updated = (
        db.query(models.StarPayment)
        .filter(
            models.StarPayment.id == payment.id,
            models.StarPayment.user_id == user.id,
            models.StarPayment.status == PAYMENT_STATUS_PAID,
        )
        .update(
            {
                models.StarPayment.status: PAYMENT_STATUS_CONSUMED,
                models.StarPayment.consumed_at: now,
                models.StarPayment.updated_at: now,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    if updated != 1:
        payment = get_user_payment(db, user=user, payment_id=payment_id)
        raise _payment_error_for_status(payment.status)

    return get_user_payment(db, user=user, payment_id=payment_id)


def restore_consumed_payment_to_paid(
    db: Session,
    *,
    user: models.User,
    payment_id: uuid.UUID,
) -> None:
    now = utcnow()
    (
        db.query(models.StarPayment)
        .filter(
            models.StarPayment.id == payment_id,
            models.StarPayment.user_id == user.id,
            models.StarPayment.status == PAYMENT_STATUS_CONSUMED,
        )
        .update(
            {
                models.StarPayment.status: PAYMENT_STATUS_PAID,
                models.StarPayment.consumed_at: None,
                models.StarPayment.updated_at: now,
                models.StarPayment.consumed_by_task_id: None,
            },
            synchronize_session=False,
        )
    )
    db.commit()


def attach_consumed_payment_task(
    db: Session,
    *,
    user: models.User,
    payment_id: uuid.UUID,
    task_id: str | None,
) -> None:
    if not task_id:
        return
    now = utcnow()
    (
        db.query(models.StarPayment)
        .filter(
            models.StarPayment.id == payment_id,
            models.StarPayment.user_id == user.id,
            models.StarPayment.status == PAYMENT_STATUS_CONSUMED,
        )
        .update(
            {
                models.StarPayment.consumed_by_task_id: str(task_id),
                models.StarPayment.updated_at: now,
            },
            synchronize_session=False,
        )
    )
    db.commit()

