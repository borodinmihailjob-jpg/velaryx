import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
# Enable insecure dev auth globally for tests so X-TG-USER-ID header is accepted.
# Security tests that need to verify auth rejection will patch settings directly.
os.environ["ALLOW_INSECURE_DEV_AUTH"] = "true"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
