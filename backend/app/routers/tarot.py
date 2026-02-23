import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..config import settings
from ..database import get_db
from ..dependencies import current_user_dep
from ..limiter import limiter
from ..tarot_engine import card_image_url

logger = logging.getLogger("astrobot.tarot")
router = APIRouter(prefix="/v1/tarot", tags=["tarot"])


@router.post("/draw", response_model=schemas.TarotSessionResponse)
def draw_tarot(
    payload: schemas.TarotDrawRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    session = services.draw_tarot_reading(
        db=db,
        user_id=user.id,
        spread_type=payload.spread_type,
        question=payload.question,
    )
    cards = services.get_tarot_session(db=db, user_id=user.id, session_id=session.id).cards
    cards_payload = services.build_tarot_cards_payload(cards)
    ai_interpretation, llm_provider = services.build_tarot_ai_interpretation(
        question=session.question,
        cards_payload=cards_payload,
    )
    hide_cards = llm_provider == "local:fallback"
    response_cards = [] if hide_cards else sorted(cards, key=lambda c: c.position)

    return schemas.TarotSessionResponse(
        session_id=session.id,
        spread_type=session.spread_type,
        question=session.question,
        created_at=session.created_at,
        ai_interpretation=ai_interpretation,
        llm_provider=llm_provider,
        cards=[
            schemas.TarotCardResponse(
                position=card.position,
                slot_label=card.slot_label,
                card_name=card.card_name,
                is_reversed=card.is_reversed,
                meaning=card.meaning,
                image_url=card_image_url(card.card_name),
                provider=settings.tarot_provider,
            )
            for card in response_cards
        ],
    )


@router.post("/premium")
@limiter.limit("5/minute")
async def draw_tarot_premium(
    request: Request,
    payload: schemas.TarotDrawRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    """Premium tarot reading via OpenRouter Gemini.

    Draws cards, enqueues ARQ background job and returns
    {"status": "pending", "task_id": "..."} — client polls /v1/tasks/{task_id}.
    """
    if not settings.openrouter_api_key:
        raise HTTPException(status_code=503, detail="Премиум LLM не настроен")

    session = services.draw_tarot_reading(
        db=db,
        user_id=user.id,
        spread_type=payload.spread_type,
        question=payload.question,
    )
    cards = services.get_tarot_session(db=db, user_id=user.id, session_id=session.id).cards
    cards_payload = services.build_tarot_cards_payload(cards)

    arq_pool = request.app.state.arq_pool
    job = await arq_pool.enqueue_job(
        "task_generate_tarot_premium",
        user_id=user.id,
        question=session.question,
        spread_type=session.spread_type,
        cards=cards_payload,
        created_at=session.created_at.isoformat(),
    )
    logger.info("Tarot premium LLM enqueued | user_id=%s | job_id=%s", user.id, job.job_id)
    return {"status": "pending", "task_id": job.job_id}


@router.get("/{session_id}", response_model=schemas.TarotSessionResponse)
def get_tarot_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    session = services.get_tarot_session(db=db, user_id=user.id, session_id=session_id)
    cards_payload = services.build_tarot_cards_payload(session.cards)
    return schemas.TarotSessionResponse(
        session_id=session.id,
        spread_type=session.spread_type,
        question=session.question,
        created_at=session.created_at,
        ai_interpretation=None,
        llm_provider=None,
        cards=[
            schemas.TarotCardResponse(
                position=card["position"],
                slot_label=card["slot_label"],
                card_name=card["card_name"],
                is_reversed=card["is_reversed"],
                meaning=card["meaning"],
                image_url=card["image_url"],
                provider=card["provider"],
            )
            for card in cards_payload
        ],
    )
