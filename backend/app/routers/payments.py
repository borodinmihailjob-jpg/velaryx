import hmac
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..dependencies import current_user_dep
from ..limiter import limiter
from .. import star_payments

router = APIRouter(prefix="/v1/payments", tags=["payments"])
logger = logging.getLogger("astrobot.payments")


def _serialize_payment_status(payment: models.StarPayment) -> schemas.StarsPaymentStatusResponse:
    return schemas.StarsPaymentStatusResponse(
        payment_id=payment.id,
        feature=payment.feature,  # type: ignore[arg-type]
        amount_stars=payment.amount_stars,
        currency=payment.currency,
        status=payment.status,
        paid_at=payment.paid_at,
        consumed_at=payment.consumed_at,
    )


def _serialize_wallet_entry(entry: models.WalletLedger) -> schemas.WalletLedgerEntryResponse:
    return schemas.WalletLedgerEntryResponse(
        id=entry.id,
        delta_stars=entry.delta_stars,
        kind=entry.kind,
        feature=entry.feature,
        task_id=entry.task_id,
        created_at=entry.created_at,
    )


def _check_internal_api_key(x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key")) -> None:
    if not settings.internal_api_key:
        raise HTTPException(status_code=503, detail="internal_api_key is not configured")
    if not x_internal_api_key or not hmac.compare_digest(x_internal_api_key, settings.internal_api_key):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/stars/catalog", response_model=schemas.StarsCatalogResponse)
async def get_stars_catalog():
    return schemas.StarsCatalogResponse(
        items=[
            schemas.StarsCatalogItem(
                feature=product.feature,  # type: ignore[arg-type]
                amount_stars=product.amount_stars,
                currency=star_payments.STARS_CURRENCY,
                title=product.title,
                description=product.description,
            )
            for product in star_payments.list_products()
        ]
    )


@router.post("/stars/invoice", response_model=schemas.StarsInvoiceResponse)
@limiter.limit("15/minute")
async def create_stars_invoice(
    request: Request,
    payload: schemas.StarsInvoiceCreateRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    payment = await star_payments.create_invoice_for_user(db, user=user, feature=payload.feature)
    logger.info(
        "Stars invoice created | tg_user_id=%s | payment_id=%s | feature=%s | amount=%s",
        user.tg_user_id,
        payment.id,
        payment.feature,
        payment.amount_stars,
    )
    return schemas.StarsInvoiceResponse(
        payment_id=payment.id,
        feature=payment.feature,  # type: ignore[arg-type]
        amount_stars=payment.amount_stars,
        currency=payment.currency,
        status=payment.status,
        invoice_link=str(payment.invoice_link or ""),
    )


@router.get("/wallet", response_model=schemas.WalletSummaryResponse)
@limiter.limit("60/minute")
async def get_wallet_summary(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    entries = star_payments.list_wallet_ledger_entries(db, user=user, limit=15)
    balance = star_payments.get_wallet_balance(db, user=user)
    return schemas.WalletSummaryResponse(
        balance_stars=balance,
        recent_entries=[_serialize_wallet_entry(item) for item in entries],
    )


@router.get("/stars/{payment_id}", response_model=schemas.StarsPaymentStatusResponse)
@limiter.limit("60/minute")
async def get_stars_payment_status(
    request: Request,
    payment_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    payment = star_payments.get_user_payment(db, user=user, payment_id=payment_id)
    return _serialize_payment_status(payment)


@router.post("/stars/{payment_id}/send-to-chat", response_model=schemas.StarsSendToChatResponse)
@limiter.limit("20/minute")
async def send_stars_payment_to_chat(
    request: Request,
    payment_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    payment = await star_payments.send_payment_invoice_to_chat(db, user=user, payment_id=payment_id)
    logger.info(
        "Stars invoice sent to chat | tg_user_id=%s | payment_id=%s | feature=%s | status=%s",
        user.tg_user_id,
        payment.id,
        payment.feature,
        payment.status,
    )
    return schemas.StarsSendToChatResponse(payment_id=payment.id, status=payment.status)


@router.post("/internal/validate-invoice", response_model=schemas.InternalPreCheckoutValidateResponse)
async def validate_invoice_for_pre_checkout(
    payload: schemas.InternalPreCheckoutValidateRequest,
    _: None = Depends(_check_internal_api_key),
    db: Session = Depends(get_db),
):
    ok, reason = star_payments.validate_invoice_for_pre_checkout(
        db,
        invoice_payload=payload.invoice_payload,
        tg_user_id=payload.tg_user_id,
    )
    return schemas.InternalPreCheckoutValidateResponse(ok=ok, reason=reason)


@router.post("/internal/telegram-success", response_model=schemas.TelegramStarsPaymentConfirmResponse)
async def telegram_payment_success_callback(
    payload: schemas.TelegramStarsPaymentConfirmRequest,
    _: None = Depends(_check_internal_api_key),
    db: Session = Depends(get_db),
):
    payment = star_payments.mark_payment_paid_from_telegram(
        db,
        invoice_payload=payload.invoice_payload,
        tg_user_id=payload.tg_user_id,
        currency=payload.currency,
        total_amount=payload.total_amount,
        telegram_payment_charge_id=payload.telegram_payment_charge_id,
        provider_payment_charge_id=payload.provider_payment_charge_id,
    )
    logger.info(
        "Stars payment confirmed | payment_id=%s | tg_user_id=%s | feature=%s | status=%s",
        payment.id,
        payment.tg_user_id,
        payment.feature,
        payment.status,
    )
    return schemas.TelegramStarsPaymentConfirmResponse(payment_id=payment.id, status=payment.status)
