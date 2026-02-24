from dataclasses import dataclass
import hmac

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .services import get_or_create_user
from .telegram_auth import verify_init_data


@dataclass
class AuthContext:
    tg_user_id: int
    validated_via_telegram: bool
    telegram_user_payload: dict | None = None


def get_auth_context(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_tg_user_id: int | None = Header(default=None, alias="X-TG-USER-ID"),
    x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
) -> AuthContext:
    if settings.internal_api_key:
        if x_internal_api_key and hmac.compare_digest(x_internal_api_key, settings.internal_api_key):
            if x_tg_user_id is None:
                raise HTTPException(status_code=401, detail="X-TG-USER-ID is required for internal auth")
            return AuthContext(tg_user_id=int(x_tg_user_id), validated_via_telegram=False, telegram_user_payload=None)

    if x_telegram_init_data:
        if not settings.bot_token:
            raise HTTPException(status_code=500, detail="BOT_TOKEN is required to validate initData")

        check = verify_init_data(
            init_data=x_telegram_init_data,
            bot_token=settings.bot_token,
            max_age_seconds=settings.telegram_init_data_max_age_seconds,
        )
        if not check.ok:
            raise HTTPException(status_code=401, detail=f"Invalid Telegram initData: {check.reason}")

        user_payload = check.payload.get("user")
        if not isinstance(user_payload, dict) or "id" not in user_payload:
            raise HTTPException(status_code=401, detail="Invalid Telegram user payload")

        return AuthContext(
            tg_user_id=int(user_payload["id"]),
            validated_via_telegram=True,
            telegram_user_payload=user_payload,
        )

    if settings.require_telegram_init_data:
        raise HTTPException(status_code=401, detail="X-Telegram-Init-Data header is required")

    if settings.allow_insecure_dev_auth and x_tg_user_id is not None:
        return AuthContext(tg_user_id=int(x_tg_user_id), validated_via_telegram=False, telegram_user_payload=None)

    raise HTTPException(status_code=401, detail="Unauthorized")


def current_user_dep(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    return get_or_create_user(db, auth.tg_user_id, telegram_user_payload=auth.telegram_user_payload)
