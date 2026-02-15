from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..database import get_db
from ..dependencies import current_user_dep

router = APIRouter(prefix="/v1", tags=["wishlist"])


@router.post("/wishlists", response_model=schemas.WishlistCreateResponse)
def create_wishlist(
    payload: schemas.WishlistCreateRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    wishlist = services.create_wishlist(
        db=db,
        owner_user_id=user.id,
        title=payload.title,
        slug=payload.slug,
        is_public=payload.is_public,
        cover_url=payload.cover_url,
    )
    return schemas.WishlistCreateResponse(
        id=wishlist.id,
        title=wishlist.title,
        slug=wishlist.slug,
        public_token=wishlist.public_token,
        is_public=wishlist.is_public,
    )


@router.post("/wishlists/{wishlist_id}/items", response_model=schemas.WishlistItemResponse)
def add_wishlist_item(
    wishlist_id: UUID,
    payload: schemas.WishlistItemCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    item = services.add_wishlist_item(
        db=db,
        user_id=user.id,
        wishlist_id=wishlist_id,
        title=payload.title,
        image_url=payload.image_url,
        budget_cents=payload.budget_cents,
    )

    return schemas.WishlistItemResponse(
        id=item.id,
        title=item.title,
        image_url=item.image_url,
        budget_cents=item.budget_cents,
        status="free",
    )


@router.get("/public/wishlists/{public_token}", response_model=schemas.PublicWishlistResponse)
def get_public_wishlist(public_token: str, db: Session = Depends(get_db)):
    wishlist = services.get_public_wishlist(db, public_token)
    items: list[schemas.WishlistItemResponse] = []

    for item in wishlist.items:
        reserved = any(r.active for r in item.reservations)
        items.append(
            schemas.WishlistItemResponse(
                id=item.id,
                title=item.title,
                image_url=item.image_url,
                budget_cents=item.budget_cents,
                status="reserved" if reserved else "free",
            )
        )

    return schemas.PublicWishlistResponse(
        id=wishlist.id,
        title=wishlist.title,
        cover_url=wishlist.cover_url,
        owner_user_id=wishlist.owner_user_id,
        items=items,
    )


@router.post(
    "/public/wishlists/{public_token}/items/{item_id}/reserve",
    response_model=schemas.ReserveResponse,
)
def reserve_item(
    public_token: str,
    item_id: UUID,
    payload: schemas.ReserveRequest,
    db: Session = Depends(get_db),
):
    reservation = services.reserve_item(
        db=db,
        public_token=public_token,
        item_id=item_id,
        reserver_tg_user_id=payload.reserver_tg_user_id,
        reserver_name=payload.reserver_name,
    )
    return schemas.ReserveResponse(reservation_id=reservation.id, status="reserved")
