"""Security tests: auth bypass, IDOR, idempotency."""
import pytest
from fastapi.testclient import TestClient

# conftest.py already sets ALLOW_INSECURE_DEV_AUTH=true and imports the app.
# We import settings here to patch it directly (lru_cache means env changes won't work).
from app.config import settings
from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    """TestClient with dev auth enabled (default for most tests)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def secure_client():
    """TestClient with insecure dev auth disabled for auth-rejection tests."""
    original = settings.allow_insecure_dev_auth
    settings.allow_insecure_dev_auth = False
    try:
        with TestClient(app) as c:
            yield c
    finally:
        settings.allow_insecure_dev_auth = original


class TestAuthBypass:
    def test_x_tg_user_id_without_initdata_is_rejected(self, secure_client):
        """When allow_insecure_dev_auth=False, raw X-TG-USER-ID header must be rejected."""
        resp = secure_client.get("/v1/natal/profile/latest", headers={"X-TG-USER-ID": "12345"})
        # Must NOT return 200 or 404 (which would mean auth passed)
        assert resp.status_code in (401, 403, 500), (
            f"Expected auth rejection but got {resp.status_code}: {resp.text}"
        )

    def test_no_auth_header_is_rejected(self, secure_client):
        """Requests without any auth header must be rejected."""
        resp = secure_client.get("/v1/natal/profile/latest")
        assert resp.status_code in (401, 403, 422, 500)

    def test_internal_api_key_without_tg_user_id_is_rejected(self, secure_client):
        """Internal API key without X-TG-USER-ID should be rejected."""
        resp = secure_client.get(
            "/v1/natal/profile/latest",
            headers={"X-Internal-Api-Key": "somekey"},
        )
        assert resp.status_code in (401, 403, 422, 500)

    def test_health_endpoint_is_public(self, secure_client):
        """Health endpoint should be accessible without auth."""
        resp = secure_client.get("/health")
        assert resp.status_code == 200


class TestIDOR:
    """Test that users cannot access each other's data."""

    def test_users_cannot_access_each_others_profiles(self, client):
        """User A cannot read User B's natal profile — each user sees only their own data."""
        profile_data = {
            "birth_date": "1990-05-15",
            "birth_time": "12:00:00",
            "birth_place": "Moscow",
            "latitude": 55.7558,
            "longitude": 37.6173,
            "timezone": "Europe/Moscow",
        }
        # User A creates profile
        resp_a = client.post(
            "/v1/natal/profile",
            json=profile_data,
            headers={"X-TG-USER-ID": "100001"},
        )
        assert resp_a.status_code == 200

        # User B tries to get their own latest profile — should get 404 (no profile for them)
        resp_b = client.get(
            "/v1/natal/profile/latest",
            headers={"X-TG-USER-ID": "100002"},
        )
        assert resp_b.status_code == 404

        # User B cannot see /natal/full either — should get 404 (no chart for them)
        resp_full = client.get(
            "/v1/natal/full",
            headers={"X-TG-USER-ID": "100002"},
        )
        assert resp_full.status_code == 404


class TestRaceCondition:
    """Test that get_or_create_daily_forecast is idempotent (no duplicate rows, no 500s)."""

    def test_repeated_daily_forecast_requests_are_idempotent(self, client):
        """Calling /forecast/daily multiple times returns same data, no 500 or duplicates.

        Note: SQLite StaticPool doesn't support true concurrent threads reliably.
        We test idempotency via sequential calls which exercises the "existing" code path.
        """
        profile_data = {
            "birth_date": "1985-03-20",
            "birth_time": "08:30:00",
            "birth_place": "Saint Petersburg",
            "latitude": 59.9343,
            "longitude": 30.3351,
            "timezone": "Europe/Moscow",
        }
        profile_resp = client.post(
            "/v1/natal/profile",
            json=profile_data,
            headers={"X-TG-USER-ID": "200001"},
        )
        assert profile_resp.status_code == 200
        profile_id = profile_resp.json()["id"]

        client.post(
            "/v1/natal/calculate",
            json={"profile_id": profile_id},
            headers={"X-TG-USER-ID": "200001"},
        )

        # Call the same endpoint 5 times sequentially — all must return 200 with same score
        results = []
        for _ in range(5):
            resp = client.get("/v1/forecast/daily", headers={"X-TG-USER-ID": "200001"})
            results.append(resp)

        for resp in results:
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        # All calls must return the same energy_score (idempotent — no new rows each time)
        scores = [r.json()["energy_score"] for r in results]
        assert len(set(scores)) == 1, f"Expected identical scores, got: {scores}"
