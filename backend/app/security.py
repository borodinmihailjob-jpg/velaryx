import secrets
from datetime import datetime, timedelta, timezone


def generate_token(prefix: str) -> str:
    return f"{prefix}{secrets.token_urlsafe(12)}"


def expiry_after_days(ttl_days: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=ttl_days)
