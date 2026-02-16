import logging

from fastapi import APIRouter, Depends

from .. import models, schemas
from ..dependencies import current_user_dep

router = APIRouter(prefix="/v1/telemetry", tags=["telemetry"])
logger = logging.getLogger("astrobot.telemetry")

VIEW_EVENT_LABELS = {
    "open_natal_screen": "Переход в экран Натальной карты",
    "open_stories_screen": "Переход в экран Сторис",
    "open_tarot_screen": "Переход в экран Таро",
}


@router.post("/event", response_model=schemas.TelemetryEventResponse)
def capture_event(
    payload: schemas.TelemetryEventRequest,
    user: models.User = Depends(current_user_dep),
):
    event_name = payload.event_name.strip().lower()
    event_label = VIEW_EVENT_LABELS.get(event_name, payload.event_name)
    logger.info(
        "UI событие | user_tg_id=%s | событие=%s | payload=%s",
        user.tg_user_id,
        event_label,
        payload.payload,
    )
    return schemas.TelemetryEventResponse(ok=True)
