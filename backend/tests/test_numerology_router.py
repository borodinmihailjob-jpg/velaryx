"""Integration tests for the /v1/numerology router."""
from unittest.mock import AsyncMock, MagicMock


HEADERS = {"X-TG-USER-ID": "501"}
VALID_PAYLOAD = {
    "full_name": "Иван Иванов",
    "birth_date": "1990-07-14",
}


def test_calculate_returns_numbers(client):
    resp = client.post("/v1/numerology/calculate", headers=HEADERS, json=VALID_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert "numbers" in data
    numbers = data["numbers"]
    for key in ("life_path", "expression", "soul_urge", "personality", "birthday", "personal_year"):
        assert key in numbers, f"Missing key: {key}"
        assert isinstance(numbers[key], int)
        assert 1 <= numbers[key] <= 33, f"{key}={numbers[key]} out of range"


def test_calculate_returns_done_without_arq(client):
    # ARQ pool is None in tests (no Redis) → status == "done"
    resp = client.post("/v1/numerology/calculate", headers=HEADERS, json=VALID_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "done"
    assert data["task_id"] is None


def test_calculate_life_path_correct(client):
    # date(1990, 7, 14): day=14→5, month=7→7, year=1990→19→10→1  → 5+7+1=13→4
    resp = client.post(
        "/v1/numerology/calculate",
        headers=HEADERS,
        json={"full_name": "Тест Тестов", "birth_date": "1990-07-14"},
    )
    assert resp.status_code == 200
    assert resp.json()["numbers"]["life_path"] == 4


def test_calculate_invalid_name_no_letters(client):
    resp = client.post(
        "/v1/numerology/calculate",
        headers=HEADERS,
        json={"full_name": "123 456", "birth_date": "1990-07-14"},
    )
    assert resp.status_code == 422


def test_calculate_name_too_short(client):
    resp = client.post(
        "/v1/numerology/calculate",
        headers=HEADERS,
        json={"full_name": "А", "birth_date": "1990-07-14"},
    )
    assert resp.status_code == 422


def test_calculate_invalid_date_too_old(client):
    resp = client.post(
        "/v1/numerology/calculate",
        headers=HEADERS,
        json={"full_name": "Иван Иванов", "birth_date": "1799-12-31"},
    )
    assert resp.status_code == 422


def test_calculate_invalid_date_future(client):
    resp = client.post(
        "/v1/numerology/calculate",
        headers=HEADERS,
        json={"full_name": "Иван Иванов", "birth_date": "2101-01-01"},
    )
    assert resp.status_code == 422


def test_calculate_requires_auth(client):
    resp = client.post("/v1/numerology/calculate", json=VALID_PAYLOAD)
    assert resp.status_code in (401, 403)


def test_calculate_with_arq_returns_pending(client):
    mock_job = MagicMock()
    mock_job.job_id = "test-job-123"
    mock_pool = MagicMock()
    mock_pool.enqueue_job = AsyncMock(return_value=mock_job)

    from app.main import app
    app.state.arq_pool = mock_pool
    try:
        resp = client.post("/v1/numerology/calculate", headers=HEADERS, json=VALID_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["task_id"] == "test-job-123"
    finally:
        app.state.arq_pool = None


def test_calculate_latin_name(client):
    resp = client.post(
        "/v1/numerology/calculate",
        headers=HEADERS,
        json={"full_name": "John Smith", "birth_date": "1985-03-15"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for key in ("life_path", "expression", "soul_urge", "personality", "birthday", "personal_year"):
        assert 1 <= data["numbers"][key] <= 33


def test_calculate_name_with_hyphen(client):
    resp = client.post(
        "/v1/numerology/calculate",
        headers=HEADERS,
        json={"full_name": "Мария-Петровна Иванова", "birth_date": "1992-05-20"},
    )
    assert resp.status_code == 200


# ── Premium endpoint tests ────────────────────────────────────────────

def test_premium_returns_503_without_openrouter_key(client):
    """Without OPENROUTER_API_KEY the endpoint returns 503."""
    from app.main import app
    from app.config import settings
    original = settings.openrouter_api_key
    settings.openrouter_api_key = None
    try:
        resp = client.post("/v1/numerology/premium", headers=HEADERS, json=VALID_PAYLOAD)
        assert resp.status_code == 503
    finally:
        settings.openrouter_api_key = original


def test_premium_returns_503_without_arq(client):
    """With a key set but no ARQ pool → 503."""
    from app.main import app
    from app.config import settings
    original = settings.openrouter_api_key
    settings.openrouter_api_key = "sk-or-test-key"
    app.state.arq_pool = None
    try:
        resp = client.post("/v1/numerology/premium", headers=HEADERS, json=VALID_PAYLOAD)
        assert resp.status_code == 503
    finally:
        settings.openrouter_api_key = original


def test_premium_requires_auth(client):
    """Premium endpoint must reject unauthenticated requests."""
    resp = client.post("/v1/numerology/premium", json=VALID_PAYLOAD)
    assert resp.status_code in (401, 403)


def test_premium_returns_pending_with_arq(client):
    """With key + arq_pool the endpoint enqueues a job and returns pending."""
    from unittest.mock import AsyncMock, MagicMock
    from app.main import app
    from app.config import settings

    mock_job = MagicMock()
    mock_job.job_id = "premium-job-456"
    mock_pool = MagicMock()
    mock_pool.enqueue_job = AsyncMock(return_value=mock_job)

    original_key = settings.openrouter_api_key
    settings.openrouter_api_key = "sk-or-test-key"
    app.state.arq_pool = mock_pool
    try:
        resp = client.post("/v1/numerology/premium", headers=HEADERS, json=VALID_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["task_id"] == "premium-job-456"
    finally:
        settings.openrouter_api_key = original_key
        app.state.arq_pool = None


def test_premium_invalid_name_rejected(client):
    """Validation errors from NumerologyCalculateRequest are passed through."""
    from app.config import settings
    original_key = settings.openrouter_api_key
    settings.openrouter_api_key = "sk-or-test-key"
    try:
        resp = client.post(
            "/v1/numerology/premium",
            headers=HEADERS,
            json={"full_name": "123", "birth_date": "1990-07-14"},
        )
        assert resp.status_code == 422
    finally:
        settings.openrouter_api_key = original_key
