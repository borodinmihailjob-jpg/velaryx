from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..database import get_db
from ..dependencies import current_user_dep, get_auth_context

router = APIRouter(prefix="/v1/users", tags=["users"])


def _user_response(user: models.User) -> schemas.UserResponse:
    return schemas.UserResponse(
        id=user.id,
        tg_user_id=user.tg_user_id,
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
        language_code=user.language_code,
        is_premium=user.is_premium,
        allows_write_to_pm=user.allows_write_to_pm,
        photo_url=user.photo_url,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_seen_at=user.last_seen_at,
    )


@router.post("/me", response_model=schemas.UserResponse)
def create_or_sync_me(
    payload: schemas.UserSyncRequest | None = None,
    db: Session = Depends(get_db),
    auth=Depends(get_auth_context),
):
    user = services.get_or_create_user(db, auth.tg_user_id, telegram_user_payload=auth.telegram_user_payload)
    if payload is not None:
        patch = payload.model_dump(exclude_unset=True)
        if patch:
            user = services.update_user_fields(db, user, patch)
    return _user_response(user)


@router.get("/me", response_model=schemas.UserResponse)
def get_me(user: models.User = Depends(current_user_dep)):
    return _user_response(user)


@router.patch("/me", response_model=schemas.UserResponse)
def patch_me(
    payload: schemas.UserPatchRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    patch = payload.model_dump(exclude_unset=True)
    if patch:
        user = services.update_user_fields(db, user, patch)
    return _user_response(user)


@router.delete("/me", response_model=schemas.UserDeleteResponse)
def delete_me(
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    stats = services.delete_user_profile_data(db=db, user_id=user.id)
    return schemas.UserDeleteResponse(
        deleted_user=bool(stats["deleted_user"]),
        deleted_birth_profiles=int(stats["deleted_birth_profiles"]),
        deleted_natal_charts=int(stats["deleted_natal_charts"]),
        deleted_daily_forecasts=int(stats["deleted_daily_forecasts"]),
        deleted_tarot_sessions=int(stats["deleted_tarot_sessions"]),
        deleted_tarot_cards=int(stats["deleted_tarot_cards"]),
    )
