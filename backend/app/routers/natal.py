from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..database import get_db
from ..dependencies import current_user_dep

router = APIRouter(prefix="/v1/natal", tags=["natal"])


@router.post("/profile", response_model=schemas.BirthProfileResponse)
def create_profile(
    payload: schemas.BirthProfileCreateRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    profile = services.create_birth_profile(
        db=db,
        user_id=user.id,
        birth_date=payload.birth_date,
        birth_time=payload.birth_time,
        birth_place=payload.birth_place,
        latitude=payload.latitude,
        longitude=payload.longitude,
        timezone_name=payload.timezone,
    )
    return schemas.BirthProfileResponse(
        id=profile.id,
        birth_date=profile.birth_date,
        birth_time=profile.birth_time,
        birth_place=profile.birth_place,
        latitude=profile.latitude,
        longitude=profile.longitude,
        timezone=profile.timezone,
    )


@router.post("/calculate", response_model=schemas.NatalChartResponse)
def calculate_natal(
    payload: schemas.NatalCalculateRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    chart = services.calculate_and_store_natal_chart(db=db, user_id=user.id, profile_id=payload.profile_id)
    return schemas.NatalChartResponse(
        id=chart.id,
        profile_id=chart.profile_id,
        sun_sign=chart.sun_sign,
        moon_sign=chart.moon_sign,
        rising_sign=chart.rising_sign,
        chart_payload=chart.chart_payload,
        created_at=chart.created_at,
    )


@router.get("/latest", response_model=schemas.NatalChartResponse)
def get_latest_natal(
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    chart = services.get_latest_natal_chart(db=db, user_id=user.id)
    return schemas.NatalChartResponse(
        id=chart.id,
        profile_id=chart.profile_id,
        sun_sign=chart.sun_sign,
        moon_sign=chart.moon_sign,
        rising_sign=chart.rising_sign,
        chart_payload=chart.chart_payload,
        created_at=chart.created_at,
    )
