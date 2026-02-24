from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    local_only_mode: bool = False
    database_url: str = "sqlite:///./astrobot.db"
    redis_url: str = "redis://localhost:6379/0"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    bot_token: str | None = None
    internal_api_key: str | None = None
    telegram_bot_api_timeout_seconds: float = 15.0
    bot_username: str = "replace_me_bot"
    mini_app_name: str = "app"
    mini_app_public_base_url: str | None = None

    require_telegram_init_data: bool = False
    allow_insecure_dev_auth: bool = False
    telegram_init_data_max_age_seconds: int = 900

    cors_origins_raw: str = ""
    astrology_ephe_path: str | None = None

    # Astrology engine provider:
    # - "swisseph": local Swiss Ephemeris engine
    # - "astrologyapi": external provider + local fallback
    astrology_provider: str = "swisseph"
    astrologyapi_base_url: str = "https://json.astrologyapi.com/v1"
    astrologyapi_user_id: str | None = None
    astrologyapi_api_key: str | None = None
    astrologyapi_house_system: str = "placidus"
    astrologyapi_timeout_seconds: float = 15.0

    # Tarot engine provider:
    # - "local": local deck
    # - "tarotapi_dev": external text meanings + local fallback
    tarot_provider: str = "local"
    tarotapi_base_url: str = "https://tarotapi.dev/api/v1"
    tarotapi_timeout_seconds: float = 10.0
    tarot_image_base_url: str = "https://raw.githubusercontent.com/metabismuth/tarot-json/master/cards"

    enable_response_localization: bool = True
    translate_via_google_free: bool = True
    translation_timeout_seconds: float = 8.0

    # Runtime LLM provider for non-premium features (currently only "openrouter").
    llm_provider: str = "openrouter"

    # OpenRouter (cloud LLM for premium features)
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Premium model (structured reports)
    openrouter_model: str = "google/gemini-2.0-flash-001"
    # Optional separate model for non-premium text generation (e.g. free model with :free suffix)
    openrouter_free_model: str | None = None
    openrouter_timeout_seconds: float = 90.0

    # Telegram Stars prices for premium reports (currency XTR)
    stars_price_natal_premium: int = 49
    stars_price_tarot_premium: int = 29
    stars_price_numerology_premium: int = 29
    stars_price_compat_premium: int = 29

    def cors_origins(self) -> list[str]:
        raw = self.cors_origins_raw.strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
