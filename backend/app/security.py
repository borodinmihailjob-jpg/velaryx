import secrets
import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from .config import settings


def generate_token(prefix: str) -> str:
    return f"{prefix}{secrets.token_urlsafe(12)}"


def expiry_after_days(ttl_days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=ttl_days)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    pad_len = (4 - len(raw) % 4) % 4
    return base64.urlsafe_b64decode(raw + ("=" * pad_len))


def _signing_secret() -> bytes:
    secret = settings.internal_api_key or settings.bot_token
    if not secret:
        raise RuntimeError("INTERNAL_API_KEY or BOT_TOKEN is required for signed links")
    return secret.encode("utf-8")


def create_signed_token(payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    signature = hmac.new(_signing_secret(), body, hashlib.sha256).digest()
    return f"{_b64url_encode(body)}.{_b64url_encode(signature)}"


def verify_signed_token(token: str) -> dict | None:
    try:
        body_part, sig_part = token.split(".", maxsplit=1)
        body = _b64url_decode(body_part)
        received_sig = _b64url_decode(sig_part)
    except Exception:
        return None

    expected_sig = hmac.new(_signing_secret(), body, hashlib.sha256).digest()
    if not hmac.compare_digest(received_sig, expected_sig):
        return None

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    expires_at = payload.get("exp")
    if expires_at is not None:
        try:
            if int(expires_at) < int(datetime.now(timezone.utc).timestamp()):
                return None
        except Exception:
            return None

    return payload
