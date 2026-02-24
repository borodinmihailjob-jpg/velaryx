import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
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

WALLET_LEDGER_KIND_TOPUP = "topup_credit"
WALLET_LEDGER_KIND_PREMIUM_DEBIT = "premium_debit"
WALLET_LEDGER_KIND_PREMIUM_REFUND = "premium_refund"


@dataclass(frozen=True)
class PremiumAccessClaim:
    source: str  # "payment" | "wallet"
    payment_id: uuid.UUID | None = None
    wallet_ledger_id: uuid.UUID | None = None


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
        "wallet_topup_29": StarProduct(
            feature="wallet_topup_29",
            amount_stars=29,
            title="Пополнение баланса на 29 ⭐",
            description="Пополнение внутреннего баланса Astrobot на 29 кредитов",
        ),
        "wallet_topup_49": StarProduct(
            feature="wallet_topup_49",
            amount_stars=49,
            title="Пополнение баланса на 49 ⭐",
            description="Пополнение внутреннего баланса Astrobot на 49 кредитов",
        ),
        "wallet_topup_99": StarProduct(
            feature="wallet_topup_99",
            amount_stars=99,
            title="Пополнение баланса на 99 ⭐",
            description="Пополнение внутреннего баланса Astrobot на 99 кредитов",
        ),
    }


def get_product(feature: str) -> StarProduct:
    product = _product_catalog().get(feature)
    if product is None:
        raise HTTPException(status_code=400, detail="Неизвестный платный продукт")
    return product


def list_products() -> list[StarProduct]:
    return list(_product_catalog().values())


def is_wallet_topup_feature(feature: str) -> bool:
    return str(feature).startswith("wallet_topup_")


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


async def _send_telegram_invoice_to_chat(
    *,
    chat_id: int,
    product: StarProduct,
    invoice_payload: str,
) -> None:
    body = {
        "chat_id": int(chat_id),
        "title": product.title,
        "description": product.description,
        "payload": invoice_payload,
        "currency": STARS_CURRENCY,
        "prices": [{"label": product.title, "amount": product.amount_stars}],
    }
    try:
        async with httpx.AsyncClient(timeout=settings.telegram_bot_api_timeout_seconds) as client:
            response = await client.post(_telegram_api_url("sendInvoice"), json=body)
        response.raise_for_status()
        payload = response.json()
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Telegram sendInvoice failed: %s", exc)
        raise HTTPException(status_code=502, detail="Не удалось отправить счёт в чат Telegram")

    if not payload.get("ok"):
        logger.warning("Telegram sendInvoice error response: %s", payload)
        raise HTTPException(status_code=502, detail="Telegram не отправил счёт в чат")


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


def get_wallet_balance(db: Session, *, user: models.User) -> int:
    db.refresh(user)
    return max(0, int(user.wallet_balance or 0))


def list_wallet_ledger_entries(
    db: Session,
    *,
    user: models.User,
    limit: int = 20,
) -> list[models.WalletLedger]:
    safe_limit = max(1, min(int(limit), 100))
    return (
        db.query(models.WalletLedger)
        .filter(models.WalletLedger.user_id == user.id)
        .order_by(models.WalletLedger.created_at.desc())
        .limit(safe_limit)
        .all()
    )


def _credit_wallet_for_paid_topup_if_needed(db: Session, *, payment: models.StarPayment) -> None:
    if not is_wallet_topup_feature(payment.feature):
        return

    existing = (
        db.query(models.WalletLedger)
        .filter(models.WalletLedger.star_payment_id == payment.id)
        .first()
    )
    if existing is not None:
        return

    now = utcnow()
    updated = (
        db.query(models.User)
        .filter(models.User.id == payment.user_id)
        .update(
            {
                models.User.wallet_balance: models.User.wallet_balance + int(payment.amount_stars),
                models.User.updated_at: now,
            },
            synchronize_session=False,
        )
    )
    if updated != 1:
        raise HTTPException(status_code=404, detail="Пользователь платежа не найден")

    ledger = models.WalletLedger(
        user_id=payment.user_id,
        tg_user_id=payment.tg_user_id,
        delta_stars=int(payment.amount_stars),
        kind=WALLET_LEDGER_KIND_TOPUP,
        feature=payment.feature,
        star_payment_id=payment.id,
        created_at=now,
        meta_payload={"source": "stars_payment"},
    )
    db.add(ledger)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def claim_wallet_balance_for_feature(
    db: Session,
    *,
    user: models.User,
    feature: str,
) -> models.WalletLedger:
    product = get_product(feature)
    cost = int(product.amount_stars)
    now = utcnow()

    updated = (
        db.query(models.User)
        .filter(
            models.User.id == user.id,
            models.User.wallet_balance >= cost,
        )
        .update(
            {
                models.User.wallet_balance: models.User.wallet_balance - cost,
                models.User.updated_at: now,
            },
            synchronize_session=False,
        )
    )
    if updated != 1:
        raise HTTPException(status_code=402, detail="Недостаточно баланса. Пополните кошелёк.")

    ledger = models.WalletLedger(
        user_id=user.id,
        tg_user_id=user.tg_user_id,
        delta_stars=-cost,
        kind=WALLET_LEDGER_KIND_PREMIUM_DEBIT,
        feature=feature,
        created_at=now,
        meta_payload={"source": "premium_report"},
    )
    db.add(ledger)
    db.commit()
    db.refresh(ledger)
    return ledger


def restore_wallet_spend(
    db: Session,
    *,
    user: models.User,
    wallet_ledger_id: uuid.UUID,
) -> None:
    debit = (
        db.query(models.WalletLedger)
        .filter(
            models.WalletLedger.id == wallet_ledger_id,
            models.WalletLedger.user_id == user.id,
            models.WalletLedger.kind == WALLET_LEDGER_KIND_PREMIUM_DEBIT,
        )
        .first()
    )
    if debit is None:
        return

    refund_exists = (
        db.query(models.WalletLedger.id)
        .filter(
            models.WalletLedger.related_ledger_id == debit.id,
            models.WalletLedger.kind == WALLET_LEDGER_KIND_PREMIUM_REFUND,
        )
        .first()
    )
    if refund_exists:
        return

    refund_amount = abs(int(debit.delta_stars or 0))
    if refund_amount <= 0:
        return

    now = utcnow()
    (
        db.query(models.User)
        .filter(models.User.id == user.id)
        .update(
            {
                models.User.wallet_balance: models.User.wallet_balance + refund_amount,
                models.User.updated_at: now,
            },
            synchronize_session=False,
        )
    )
    refund = models.WalletLedger(
        user_id=user.id,
        tg_user_id=user.tg_user_id,
        delta_stars=refund_amount,
        kind=WALLET_LEDGER_KIND_PREMIUM_REFUND,
        feature=debit.feature,
        related_ledger_id=debit.id,
        created_at=now,
        meta_payload={"reason": "enqueue_failed"},
    )
    db.add(refund)
    db.commit()


def attach_wallet_spend_task(
    db: Session,
    *,
    user: models.User,
    wallet_ledger_id: uuid.UUID,
    task_id: str | None,
) -> None:
    if not task_id:
        return
    (
        db.query(models.WalletLedger)
        .filter(
            models.WalletLedger.id == wallet_ledger_id,
            models.WalletLedger.user_id == user.id,
            models.WalletLedger.kind == WALLET_LEDGER_KIND_PREMIUM_DEBIT,
        )
        .update(
            {
                models.WalletLedger.task_id: str(task_id),
            },
            synchronize_session=False,
        )
    )
    db.commit()


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
    _credit_wallet_for_paid_topup_if_needed(db, payment=payment)
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


def claim_premium_access(
    db: Session,
    *,
    user: models.User,
    feature: str,
    payment_id: uuid.UUID | None = None,
    use_wallet: bool = False,
) -> PremiumAccessClaim:
    if payment_id is not None:
        payment = claim_paid_payment_for_feature(db, user=user, feature=feature, payment_id=payment_id)
        return PremiumAccessClaim(source="payment", payment_id=payment.id)
    if use_wallet:
        entry = claim_wallet_balance_for_feature(db, user=user, feature=feature)
        return PremiumAccessClaim(source="wallet", wallet_ledger_id=entry.id)
    raise HTTPException(status_code=402, detail="Для премиум-отчёта нужна оплата Stars или баланс кошелька")


def restore_premium_access_claim(
    db: Session,
    *,
    user: models.User,
    claim: PremiumAccessClaim | None,
) -> None:
    if claim is None:
        return
    if claim.source == "payment" and claim.payment_id is not None:
        restore_consumed_payment_to_paid(db, user=user, payment_id=claim.payment_id)
        return
    if claim.source == "wallet" and claim.wallet_ledger_id is not None:
        restore_wallet_spend(db, user=user, wallet_ledger_id=claim.wallet_ledger_id)


def attach_premium_claim_task(
    db: Session,
    *,
    user: models.User,
    claim: PremiumAccessClaim | None,
    task_id: str | None,
) -> None:
    if claim is None or not task_id:
        return
    if claim.source == "payment" and claim.payment_id is not None:
        attach_consumed_payment_task(db, user=user, payment_id=claim.payment_id, task_id=task_id)
        return
    if claim.source == "wallet" and claim.wallet_ledger_id is not None:
        attach_wallet_spend_task(db, user=user, wallet_ledger_id=claim.wallet_ledger_id, task_id=task_id)


async def send_payment_invoice_to_chat(
    db: Session,
    *,
    user: models.User,
    payment_id: uuid.UUID,
) -> models.StarPayment:
    payment = get_user_payment(db, user=user, payment_id=payment_id)
    if payment.status == PAYMENT_STATUS_CONSUMED:
        raise HTTPException(status_code=409, detail="Платёж уже использован")
    if payment.status in {PAYMENT_STATUS_PAID}:
        return payment
    if payment.status in {PAYMENT_STATUS_FAILED, PAYMENT_STATUS_CANCELLED}:
        raise HTTPException(status_code=409, detail="Платёж недоступен для повторной отправки")

    product = get_product(payment.feature)
    await _send_telegram_invoice_to_chat(
        chat_id=user.tg_user_id,
        product=product,
        invoice_payload=payment.invoice_payload,
    )

    if payment.status == PAYMENT_STATUS_CREATED:
        payment.status = PAYMENT_STATUS_INVOICED
    payment.updated_at = utcnow()
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment
