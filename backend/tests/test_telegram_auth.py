import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from app.config import settings
from app.telegram_auth import verify_init_data


def test_verify_init_data_success():
    bot_token = "123456:ABCDEF_TOKEN"
    payload = {
        "auth_date": str(int(time.time())),
        "query_id": "AAEAAAE",
        "user": json.dumps({"id": 777001, "first_name": "M"}, separators=(",", ":")),
    }

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    payload_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    init_data = urlencode({**payload, "hash": payload_hash})

    result = verify_init_data(init_data=init_data, bot_token=bot_token, max_age_seconds=120)
    assert result.ok is True
    assert result.payload["user"]["id"] == 777001


def test_verify_init_data_invalid_hash():
    result = verify_init_data(
        init_data="auth_date=100&user=%7B%22id%22%3A1%7D&hash=broken",
        bot_token="123456:ABCDEF_TOKEN",
        max_age_seconds=120,
    )
    assert result.ok is False


def test_internal_api_key_auth(client):
    original_require = settings.require_telegram_init_data
    original_key = settings.internal_api_key
    settings.require_telegram_init_data = True
    settings.internal_api_key = "internal-secret"

    try:
        response = client.post(
            "/v1/compat/invites",
            headers={"X-TG-USER-ID": "900", "X-Internal-API-Key": "internal-secret"},
            json={"ttl_days": 7, "max_uses": 1},
        )
        assert response.status_code == 200
    finally:
        settings.require_telegram_init_data = original_require
        settings.internal_api_key = original_key
