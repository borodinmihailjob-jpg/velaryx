import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..database import get_db
from ..dependencies import current_user_dep

router = APIRouter(prefix="/v1/natal", tags=["natal"])
logger = logging.getLogger("astrobot.natal")


@router.post("/profile", response_model=schemas.BirthProfileResponse)
def create_profile(
    payload: schemas.BirthProfileCreateRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    logger.info(
        "Ввод данных натала | user_tg_id=%s | дата=%s | время=%s | место=%s | lat=%.5f | lon=%.5f | tz=%s",
        user.tg_user_id,
        payload.birth_date,
        payload.birth_time,
        payload.birth_place,
        payload.latitude,
        payload.longitude,
        payload.timezone,
    )
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


@router.delete("/profile", response_model=schemas.ProfileDeleteResponse)
def delete_profile(
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    tg_user_id = user.tg_user_id
    stats = services.delete_user_profile_data(db=db, user_id=user.id)
    logger.info(
        "Полный сброс профиля пользователя | user_tg_id=%s | removed=%s",
        tg_user_id,
        stats,
    )
    return schemas.ProfileDeleteResponse(
        deleted_user=bool(stats["deleted_user"]),
        deleted_birth_profiles=int(stats["deleted_birth_profiles"]),
        deleted_natal_charts=int(stats["deleted_natal_charts"]),
        deleted_daily_forecasts=int(stats["deleted_daily_forecasts"]),
        deleted_tarot_sessions=int(stats["deleted_tarot_sessions"]),
        deleted_tarot_cards=int(stats["deleted_tarot_cards"]),
    )


@router.get("/profile/latest", response_model=schemas.BirthProfileResponse)
def get_latest_profile(
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    profile = services.get_latest_birth_profile(db=db, user_id=user.id)
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
    logger.info(
        "Запуск расчёта натальной карты | user_tg_id=%s | profile_id=%s",
        user.tg_user_id,
        payload.profile_id,
    )
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


@router.get("/full", response_model=schemas.NatalFullResponse)
def get_full_natal(
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    chart, sections, wheel_chart_url = services.get_full_natal_chart(db=db, user_id=user.id)
    return schemas.NatalFullResponse(
        id=chart.id,
        profile_id=chart.profile_id,
        sun_sign=chart.sun_sign,
        moon_sign=chart.moon_sign,
        rising_sign=chart.rising_sign,
        chart_payload=chart.chart_payload,
        interpretation_sections=sections,
        wheel_chart_url=wheel_chart_url,
        created_at=chart.created_at,
    )
