from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..database import get_db
from ..dependencies import current_user_dep

router = APIRouter(prefix="/v1/insights", tags=["insights"])


@router.post("/astro-tarot", response_model=schemas.ComboInsightResponse)
def astro_tarot_insight(
    payload: schemas.ComboInsightRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    chart, forecast, session, cards, combined_advice, llm_provider = services.build_combo_insight(
        db=db,
        user_id=user.id,
        question=payload.question,
        spread_type=payload.spread_type,
    )

    natal_summary = ""
    if isinstance(chart.chart_payload, dict):
        natal_summary = str(chart.chart_payload.get("interpretation", {}).get("summary") or "")

    return schemas.ComboInsightResponse(
        question=payload.question,
        natal_summary=natal_summary,
        daily_summary=forecast.summary,
        tarot_session_id=session.id,
        llm_provider=llm_provider,
        tarot_cards=[
            schemas.TarotCardResponse(
                position=card["position"],
                slot_label=card["slot_label"],
                card_name=card["card_name"],
                is_reversed=card["is_reversed"],
                meaning=card["meaning"],
                image_url=card["image_url"],
                provider=card["provider"],
            )
            for card in cards
        ],
        combined_advice=combined_advice,
    )
