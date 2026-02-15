import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


@dataclass
class TelegramAuthResult:
    ok: bool
    reason: str | None
    payload: dict


def _build_data_check_string(payload: dict[str, str]) -> str:
    parts: list[str] = []
    for key in sorted(payload.keys()):
        parts.append(f"{key}={payload[key]}")
    return "\n".join(parts)


def verify_init_data(init_data: str, bot_token: str, max_age_seconds: int) -> TelegramAuthResult:
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return TelegramAuthResult(ok=False, reason="Missing hash", payload={})

    data_check_string = _build_data_check_string(parsed)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        return TelegramAuthResult(ok=False, reason="Hash mismatch", payload={})

    auth_date_raw = parsed.get("auth_date")
    if not auth_date_raw:
        return TelegramAuthResult(ok=False, reason="Missing auth_date", payload={})

    try:
        auth_date = int(auth_date_raw)
    except ValueError:
        return TelegramAuthResult(ok=False, reason="Invalid auth_date", payload={})

    if int(time.time()) - auth_date > max_age_seconds:
        return TelegramAuthResult(ok=False, reason="initData expired", payload={})

    decoded_payload: dict = dict(parsed)
    if "user" in decoded_payload:
        try:
            decoded_payload["user"] = json.loads(decoded_payload["user"])
        except json.JSONDecodeError:
            return TelegramAuthResult(ok=False, reason="Invalid user payload", payload={})

    return TelegramAuthResult(ok=True, reason=None, payload=decoded_payload)
