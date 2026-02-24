"""Redis-backed user report history (14-day TTL)."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("astrobot.history")

_REPORT_TTL = 14 * 24 * 3600  # 14 days in seconds
_INDEX_TTL = 30 * 24 * 3600   # 30 days for the sorted-set index


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def save_report_to_history(
    redis: Any,
    tg_user_id: int,
    report_type: str,
    report_id: str,
    is_premium: bool,
    summary: dict,
) -> None:
    """Persist a report summary to Redis with 14-day TTL.

    Key schema:
        user_report:{tg_user_id}:{report_type}:{report_id}  →  JSON blob (SETEX 14d)
        user_history:{tg_user_id}  →  Sorted Set score=unix_ts member="{report_type}:{report_id}"
    """
    if redis is None:
        return
    try:
        blob = json.dumps(
            {
                "type": report_type,
                "id": report_id,
                "is_premium": is_premium,
                "summary": summary,
                "created_at": _utcnow_iso(),
            },
            ensure_ascii=False,
        )
        report_key = f"user_report:{tg_user_id}:{report_type}:{report_id}"
        history_key = f"user_history:{tg_user_id}"
        member = f"{report_type}:{report_id}"

        await redis.setex(report_key, _REPORT_TTL, blob)
        await redis.zadd(history_key, {member: time.time()})
        await redis.expire(history_key, _INDEX_TTL)
    except Exception:
        logger.exception("Failed to save report to history | tg_user_id=%s | type=%s", tg_user_id, report_type)


async def get_user_history(redis: Any, tg_user_id: int) -> list[dict]:
    """Return reports from the last 14 days, sorted newest-first.

    Cleans up expired index entries on each read.
    Returns [] on any Redis error.
    """
    if redis is None:
        return []
    try:
        history_key = f"user_history:{tg_user_id}"
        cutoff = time.time() - _REPORT_TTL

        # Fetch members from the last 14 days
        members: list[bytes | str] = await redis.zrangebyscore(history_key, cutoff, "+inf")

        if not members:
            return []

        # Fetch all report blobs in one round-trip
        keys = [f"user_report:{tg_user_id}:{m.decode() if isinstance(m, bytes) else m}" for m in members]
        values = await redis.mget(*keys)

        reports: list[dict] = []
        for raw in values:
            if raw is None:
                continue
            try:
                reports.append(json.loads(raw.decode() if isinstance(raw, bytes) else raw))
            except Exception:
                pass

        # Clean stale index entries in background (fire-and-forget)
        try:
            await redis.zremrangebyscore(history_key, "-inf", cutoff - 1)
        except Exception:
            pass

        # Sort newest-first
        reports.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return reports

    except Exception:
        logger.exception("Failed to read user history | tg_user_id=%s", tg_user_id)
        return []
