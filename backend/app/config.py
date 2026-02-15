from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./astrobot.db"
    redis_url: str = "redis://localhost:6379/0"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    bot_token: str | None = None
    internal_api_key: str | None = None
    bot_username: str = "replace_me_bot"
    mini_app_name: str = "app"
    mini_app_public_base_url: str | None = None

    require_telegram_init_data: bool = False
    allow_insecure_dev_auth: bool = True
    telegram_init_data_max_age_seconds: int = 900

    cors_origins_raw: str = ""
    astrology_ephe_path: str | None = None

    # Astrology engine provider:
    # - "swisseph": local Swiss Ephemeris engine
    # - "astrologyapi": external provider + local fallback
    astrology_provider: str = "astrologyapi"
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

    def cors_origins(self) -> list[str]:
        raw = self.cors_origins_raw.strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
