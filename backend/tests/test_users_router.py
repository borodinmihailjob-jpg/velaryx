import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from app.config import settings


def _build_init_data(*, bot_token: str, user_payload: dict) -> str:
    payload = {
        "auth_date": str(int(time.time())),
        "query_id": "AAE_TEST_QUERY",
        "user": json.dumps(user_payload, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    payload_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    return urlencode({**payload, "hash": payload_hash})


def test_users_me_crud(client):
    headers = {"X-TG-USER-ID": "424242"}

    create_resp = client.post(
        "/v1/users/me",
        headers=headers,
        json={
            "first_name": "Mihail",
            "last_name": "Borodin",
            "username": "mihail_dev",
            "language_code": "ru",
        },
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["tg_user_id"] == 424242
    assert created["first_name"] == "Mihail"
    first_user_id = created["id"]

    get_resp = client.get("/v1/users/me", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["username"] == "mihail_dev"

    patch_resp = client.patch(
        "/v1/users/me",
        headers=headers,
        json={"last_name": None, "language_code": "en"},
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["last_name"] is None
    assert patched["language_code"] == "en"

    delete_resp = client.delete("/v1/users/me", headers=headers)
    assert delete_resp.status_code == 200
    deleted = delete_resp.json()
    assert deleted["ok"] is True
    assert deleted["deleted_user"] is True

    recreated_resp = client.get("/v1/users/me", headers=headers)
    assert recreated_resp.status_code == 200
    recreated = recreated_resp.json()
    assert recreated["tg_user_id"] == 424242
    assert recreated["first_name"] is None  # fresh user — no profile data


def test_users_me_syncs_telegram_init_data(client):
    original_bot_token = settings.bot_token
    bot_token = "123456:TEST_BOT_TOKEN"
    settings.bot_token = bot_token
    try:
        init_data = _build_init_data(
            bot_token=bot_token,
            user_payload={
                "id": 700001,
                "first_name": "Ivan",
                "last_name": "Petrov",
                "username": "ivan_petrov",
                "language_code": "ru",
                "is_premium": True,
            },
        )
        response = client.get("/v1/users/me", headers={"X-Telegram-Init-Data": init_data})
        assert response.status_code == 200
        data = response.json()
        assert data["tg_user_id"] == 700001
        assert data["first_name"] == "Ivan"
        assert data["language_code"] == "ru"
        assert data["is_premium"] is True
        assert data["last_seen_at"] is not None
    finally:
        settings.bot_token = original_bot_token
