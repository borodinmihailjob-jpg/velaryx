from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field


class BirthProfileCreateRequest(BaseModel):
    birth_date: date
    birth_time: time
    birth_place: str = Field(min_length=1, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str = Field(min_length=3, max_length=64)


class BirthProfileResponse(BaseModel):
    id: UUID
    birth_date: date
    birth_time: time
    birth_place: str
    latitude: float
    longitude: float
    timezone: str


class NatalCalculateRequest(BaseModel):
    profile_id: UUID


class NatalChartResponse(BaseModel):
    id: UUID
    profile_id: UUID
    sun_sign: str
    moon_sign: str
    rising_sign: str
    chart_payload: dict
    created_at: datetime


class NatalFullResponse(BaseModel):
    id: UUID
    profile_id: UUID
    sun_sign: str
    moon_sign: str
    rising_sign: str
    chart_payload: dict
    interpretation_sections: list[dict]
    wheel_chart_url: str | None = None
    created_at: datetime


class ForecastDailyResponse(BaseModel):
    date: date
    energy_score: int
    summary: str
    payload: dict


class ForecastStorySlide(BaseModel):
    title: str
    body: str
    badge: str | None = None
    tip: str | None = None
    avoid: str | None = None
    timing: str | None = None
    animation: str | None = None


class ForecastStoriesResponse(BaseModel):
    date: date
    slides: list[ForecastStorySlide]
    llm_provider: str | None = None


class TarotDrawRequest(BaseModel):
    spread_type: str = Field(default="three_card")
    question: str | None = Field(default=None, max_length=500)


class TarotCardResponse(BaseModel):
    position: int
    slot_label: str
    card_name: str
    is_reversed: bool
    meaning: str
    image_url: str | None = None
    provider: str | None = None


class TarotSessionResponse(BaseModel):
    session_id: UUID
    spread_type: str
    question: str | None
    created_at: datetime
    cards: list[TarotCardResponse]
    ai_interpretation: str | None = None
    llm_provider: str | None = None


class TelemetryEventRequest(BaseModel):
    event_name: str = Field(min_length=1, max_length=100)
    payload: dict = Field(default_factory=dict)


class TelemetryEventResponse(BaseModel):
    ok: bool = True
