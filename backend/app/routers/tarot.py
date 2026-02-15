from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..config import settings
from ..database import get_db
from ..dependencies import current_user_dep
from ..tarot_engine import card_image_url

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

    return schemas.TarotSessionResponse(
        session_id=session.id,
        spread_type=session.spread_type,
        question=session.question,
        created_at=session.created_at,
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
            for card in sorted(cards, key=lambda c: c.position)
        ],
    )


@router.get("/{session_id}", response_model=schemas.TarotSessionResponse)
def get_tarot_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    session = services.get_tarot_session(db=db, user_id=user.id, session_id=session_id)
    return schemas.TarotSessionResponse(
        session_id=session.id,
        spread_type=session.spread_type,
        question=session.question,
        created_at=session.created_at,
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
            for card in sorted(session.cards, key=lambda c: c.position)
        ],
    )
