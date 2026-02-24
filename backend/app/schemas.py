from datetime import date, datetime, time
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class BirthProfileCreateRequest(BaseModel):
    birth_date: date
    birth_time: time
    birth_place: str = Field(min_length=1, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str = Field(min_length=3, max_length=64)

    @field_validator("birth_date")
    @classmethod
    def birth_date_in_range(cls, v: date) -> date:
        if v.year < 1800 or v.year > 2100:
            raise ValueError("birth_date must be between 1800 and 2100")
        return v


_VALID_MBTI = {
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
}


class UserSyncRequest(BaseModel):
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)
    language_code: str | None = Field(default=None, max_length=16)
    is_premium: bool | None = None
    allows_write_to_pm: bool | None = None
    photo_url: str | None = Field(default=None, max_length=1000)
    mbti_type: str | None = Field(default=None, max_length=4)

    @field_validator("mbti_type")
    @classmethod
    def mbti_type_valid(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().upper()
        if v not in _VALID_MBTI:
            raise ValueError(f"mbti_type must be one of {sorted(_VALID_MBTI)}")
        return v

    @field_validator("first_name", "last_name", "username", "language_code", "photo_url")
    @classmethod
    def strip_optional_strings(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class UserPatchRequest(UserSyncRequest):
    pass


class UserResponse(BaseModel):
    id: int
    tg_user_id: int
    first_name: str | None
    last_name: str | None
    username: str | None
    language_code: str | None
    is_premium: bool | None
    allows_write_to_pm: bool | None
    photo_url: str | None
    mbti_type: str | None
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None


class UserDeleteResponse(BaseModel):
    ok: bool = True
    deleted_user: bool
    deleted_birth_profiles: int
    deleted_natal_charts: int
    deleted_daily_forecasts: int
    deleted_tarot_sessions: int
    deleted_tarot_cards: int


class BirthProfileResponse(BaseModel):
    id: UUID
    birth_date: date
    birth_time: time
    birth_place: str
    latitude: float
    longitude: float
    timezone: str


class ProfileDeleteResponse(BaseModel):
    ok: bool = True
    deleted_user: bool
    deleted_birth_profiles: int
    deleted_natal_charts: int
    deleted_daily_forecasts: int
    deleted_tarot_sessions: int
    deleted_tarot_cards: int


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
    spread_type: Literal["one_card", "three_card", "relationship", "career"] = "three_card"
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


class TaskStatusResponse(BaseModel):
    status: Literal["pending", "done", "failed"]
    result: dict[str, Any] | None = None
    error: str | None = None


PremiumFeatureCode = Literal["natal_premium", "tarot_premium", "numerology_premium"]


class StarsCatalogItem(BaseModel):
    feature: PremiumFeatureCode
    amount_stars: int
    currency: Literal["XTR"] = "XTR"
    title: str
    description: str


class StarsCatalogResponse(BaseModel):
    items: list[StarsCatalogItem]


class StarsInvoiceCreateRequest(BaseModel):
    feature: PremiumFeatureCode


class StarsInvoiceResponse(BaseModel):
    payment_id: UUID
    feature: PremiumFeatureCode
    amount_stars: int
    currency: str
    status: str
    invoice_link: str


class StarsPaymentStatusResponse(BaseModel):
    payment_id: UUID
    feature: PremiumFeatureCode
    amount_stars: int
    currency: str
    status: str
    paid_at: datetime | None = None
    consumed_at: datetime | None = None


class TelegramStarsPaymentConfirmRequest(BaseModel):
    invoice_payload: str = Field(min_length=1, max_length=128)
    tg_user_id: int | None = None
    currency: str = Field(min_length=1, max_length=8)
    total_amount: int = Field(ge=1)
    telegram_payment_charge_id: str | None = Field(default=None, max_length=255)
    provider_payment_charge_id: str | None = Field(default=None, max_length=255)


class TelegramStarsPaymentConfirmResponse(BaseModel):
    ok: bool = True
    payment_id: UUID
    status: str


class NumerologyCalculateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    birth_date: date

    @field_validator("birth_date")
    @classmethod
    def birth_date_in_range(cls, v: date) -> date:
        if v.year < 1800 or v.year > 2100:
            raise ValueError("birth_date must be between 1800 and 2100")
        return v

    @field_validator("full_name")
    @classmethod
    def name_must_have_letters(cls, v: str) -> str:
        letters = [c for c in v if c.isalpha()]
        if len(letters) < 2:
            raise ValueError("full_name must contain at least 2 letters")
        return v.strip()


class NumerologyNumbers(BaseModel):
    life_path: int
    expression: int
    soul_urge: int
    personality: int
    birthday: int
    personal_year: int


class NumerologyCalculateResponse(BaseModel):
    numbers: NumerologyNumbers
    status: Literal["pending", "done"]
    task_id: str | None = None
