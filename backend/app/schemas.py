from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field


class CompatInviteCreateRequest(BaseModel):
    ttl_days: int = Field(default=7, ge=1, le=90)
    max_uses: int = Field(default=1, ge=1, le=100)


class CompatInviteCreateResponse(BaseModel):
    token: str
    expires_at: datetime


class CompatStartRequest(BaseModel):
    invite_token: str


class CompatStartResponse(BaseModel):
    session_id: UUID
    score: int
    summary: str
    strengths: list[str] = Field(default_factory=list)
    growth_areas: list[str] = Field(default_factory=list)


class WishlistCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=128)
    is_public: bool = True
    cover_url: str | None = None


class WishlistItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    image_url: str | None = None
    budget_cents: int | None = Field(default=None, ge=0)


class WishlistItemResponse(BaseModel):
    id: UUID
    title: str
    image_url: str | None
    budget_cents: int | None
    status: str


class WishlistCreateResponse(BaseModel):
    id: UUID
    title: str
    slug: str
    public_token: str
    is_public: bool


class PublicWishlistResponse(BaseModel):
    id: UUID
    title: str
    cover_url: str | None
    owner_user_id: int
    items: list[WishlistItemResponse]


class ReserveRequest(BaseModel):
    reserver_tg_user_id: int | None = None
    reserver_name: str | None = Field(default=None, max_length=200)


class ReserveResponse(BaseModel):
    reservation_id: UUID
    status: str


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


class ForecastStoriesResponse(BaseModel):
    date: date
    slides: list[ForecastStorySlide]


class ComboInsightRequest(BaseModel):
    question: str | None = Field(default=None, max_length=500)
    spread_type: str = Field(default="three_card")


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


class ComboInsightResponse(BaseModel):
    question: str | None
    natal_summary: str
    daily_summary: str
    tarot_session_id: UUID
    llm_provider: str | None = None
    tarot_cards: list[TarotCardResponse]
    combined_advice: str


class ReportLinkResponse(BaseModel):
    url: str
    expires_at: datetime
