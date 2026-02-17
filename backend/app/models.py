import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

INT64 = BigInteger().with_variant(Integer, "sqlite")



def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(INT64, primary_key=True, autoincrement=True)
    tg_user_id: Mapped[int] = mapped_column(INT64, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class BirthProfile(Base):
    __tablename__ = "birth_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(INT64, ForeignKey("users.id"), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    birth_time: Mapped[time] = mapped_column(Time, nullable=False)
    birth_place: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped[User] = relationship("User")


class NatalChart(Base):
    __tablename__ = "natal_charts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("birth_profiles.id"), nullable=False)
    sun_sign: Mapped[str] = mapped_column(String(32), nullable=False)
    moon_sign: Mapped[str] = mapped_column(String(32), nullable=False)
    rising_sign: Mapped[str] = mapped_column(String(32), nullable=False)
    chart_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    profile: Mapped[BirthProfile] = relationship("BirthProfile")


class DailyForecast(Base):
    __tablename__ = "daily_forecasts"
    __table_args__ = (UniqueConstraint("user_id", "forecast_date", name="uq_forecast_user_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(INT64, ForeignKey("users.id"), nullable=False)
    forecast_date: Mapped[date] = mapped_column(Date, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    energy_score: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TarotSession(Base):
    __tablename__ = "tarot_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int | None] = mapped_column(INT64, ForeignKey("users.id"))
    spread_type: Mapped[str] = mapped_column(String(32), nullable=False)
    question: Mapped[str | None] = mapped_column(Text)
    seed: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    cards: Mapped[list["TarotCard"]] = relationship(
        "TarotCard", back_populates="session", cascade="all, delete-orphan"
    )


class TarotCard(Base):
    __tablename__ = "tarot_cards"
    __table_args__ = (UniqueConstraint("session_id", "position", name="uq_tarot_session_position"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tarot_sessions.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_label: Mapped[str] = mapped_column(String(64), nullable=False)
    card_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_reversed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    meaning: Mapped[str] = mapped_column(Text, nullable=False)

    session: Mapped[TarotSession] = relationship("TarotSession", back_populates="cards")
