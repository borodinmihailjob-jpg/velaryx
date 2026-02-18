"""Input validation tests.

conftest.py sets DATABASE_URL=sqlite and ALLOW_INSECURE_DEV_AUTH=true before
importing the app, so we don't need to repeat that here.
"""
import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app

HEADERS = {"X-TG-USER-ID": "301"}


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


class TestBirthProfileValidation:
    def test_invalid_latitude_rejected(self, client):
        resp = client.post(
            "/v1/natal/profile",
            json={
                "birth_date": "1990-01-01",
                "birth_time": "12:00:00",
                "birth_place": "Moscow",
                "latitude": 200.0,  # invalid
                "longitude": 37.6,
                "timezone": "Europe/Moscow",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 422

    def test_invalid_longitude_rejected(self, client):
        resp = client.post(
            "/v1/natal/profile",
            json={
                "birth_date": "1990-01-01",
                "birth_time": "12:00:00",
                "birth_place": "Moscow",
                "latitude": 55.7,
                "longitude": 999.0,  # invalid
                "timezone": "Europe/Moscow",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 422

    def test_empty_birth_place_rejected(self, client):
        resp = client.post(
            "/v1/natal/profile",
            json={
                "birth_date": "1990-01-01",
                "birth_time": "12:00:00",
                "birth_place": "",  # invalid
                "latitude": 55.7,
                "longitude": 37.6,
                "timezone": "Europe/Moscow",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 422

    def test_birth_date_year_below_range_rejected(self, client):
        resp = client.post(
            "/v1/natal/profile",
            json={
                "birth_date": "1799-12-31",  # below 1800
                "birth_time": "12:00:00",
                "birth_place": "Moscow",
                "latitude": 55.7,
                "longitude": 37.6,
                "timezone": "Europe/Moscow",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 422

    def test_birth_date_year_above_range_rejected(self, client):
        resp = client.post(
            "/v1/natal/profile",
            json={
                "birth_date": "2101-01-01",  # above 2100
                "birth_time": "12:00:00",
                "birth_place": "Moscow",
                "latitude": 55.7,
                "longitude": 37.6,
                "timezone": "Europe/Moscow",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 422

    def test_valid_profile_accepted(self, client):
        resp = client.post(
            "/v1/natal/profile",
            json={
                "birth_date": "1990-06-15",
                "birth_time": "14:30:00",
                "birth_place": "Moscow",
                "latitude": 55.7558,
                "longitude": 37.6173,
                "timezone": "Europe/Moscow",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 200


class TestTarotValidation:
    def test_invalid_spread_type_rejected(self, client):
        # First create profile and chart
        client.post(
            "/v1/natal/profile",
            json={
                "birth_date": "1990-01-01",
                "birth_time": "12:00:00",
                "birth_place": "Moscow",
                "latitude": 55.7558,
                "longitude": 37.6173,
                "timezone": "Europe/Moscow",
            },
            headers=HEADERS,
        )
        resp = client.post(
            "/v1/tarot/draw",
            json={"spread_type": "invalid_spread_xyz", "question": "test"},
            headers=HEADERS,
        )
        assert resp.status_code == 422

    def test_question_too_long_rejected(self, client):
        resp = client.post(
            "/v1/tarot/draw",
            json={"spread_type": "three_card", "question": "x" * 501},
            headers=HEADERS,
        )
        assert resp.status_code == 422

    def test_valid_spread_types_accepted(self, client):
        # Create profile first
        profile_resp = client.post(
            "/v1/natal/profile",
            json={
                "birth_date": "1990-01-01",
                "birth_time": "12:00:00",
                "birth_place": "Moscow",
                "latitude": 55.7558,
                "longitude": 37.6173,
                "timezone": "Europe/Moscow",
            },
            headers=HEADERS,
        )
        assert profile_resp.status_code == 200
        profile_id = profile_resp.json()["id"]
        client.post("/v1/natal/calculate", json={"profile_id": profile_id}, headers=HEADERS)

        for spread in ("one_card", "three_card"):
            resp = client.post(
                "/v1/tarot/draw",
                json={"spread_type": spread},
                headers=HEADERS,
            )
            assert resp.status_code == 200, f"Spread {spread} returned {resp.status_code}: {resp.text}"
