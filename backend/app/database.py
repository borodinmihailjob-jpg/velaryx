from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import settings


class Base(DeclarativeBase):
    pass


engine_kwargs: dict = {}
connect_args: dict = {}

if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    if ":memory:" in settings.database_url:
        engine_kwargs["poolclass"] = StaticPool
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
    engine_kwargs["pool_timeout"] = 30

engine = create_engine(
    settings.database_url,
    future=True,
    connect_args=connect_args,
    **engine_kwargs,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
