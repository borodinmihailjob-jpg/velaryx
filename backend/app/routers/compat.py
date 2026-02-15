from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas, services
from ..database import get_db
from ..dependencies import current_user_dep
from ..models import User

router = APIRouter(prefix="/v1/compat", tags=["compatibility"])


@router.post("/invites", response_model=schemas.CompatInviteCreateResponse)
def create_invite(
    payload: schemas.CompatInviteCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user_dep),
):
    invite = services.create_compat_invite(
        db=db,
        inviter_user_id=user.id,
        ttl_days=payload.ttl_days,
        max_uses=payload.max_uses,
    )
    return schemas.CompatInviteCreateResponse(token=invite.token, expires_at=invite.expires_at)


@router.post("/start", response_model=schemas.CompatStartResponse)
def start_compat(
    payload: schemas.CompatStartRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user_dep),
):
    session, result = services.start_compat_session(
        db=db,
        invite_token=payload.invite_token,
        invitee_user_id=user.id,
    )
    return schemas.CompatStartResponse(
        session_id=session.id,
        score=result.score,
        summary=result.summary,
    )
