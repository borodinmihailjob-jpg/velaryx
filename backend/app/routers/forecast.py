from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..database import get_db
from ..dependencies import current_user_dep

router = APIRouter(prefix="/v1/forecast", tags=["forecast"])


@router.get("/daily", response_model=schemas.ForecastDailyResponse)
def get_daily_forecast(
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    forecast = services.get_or_create_daily_forecast(
        db=db,
        user_id=user.id,
        forecast_date=date.today(),
    )
    return schemas.ForecastDailyResponse(
        date=forecast.forecast_date,
        energy_score=forecast.energy_score,
        summary=forecast.summary,
        payload=forecast.payload,
    )


@router.get("/stories", response_model=schemas.ForecastStoriesResponse)
def get_forecast_stories(
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    chart = services.get_latest_natal_chart(db=db, user_id=user.id)
    forecast = services.get_or_create_daily_forecast(
        db=db,
        user_id=user.id,
        forecast_date=date.today(),
    )
    slides, llm_provider = services.build_forecast_story_slides(chart=chart, forecast=forecast)
    return schemas.ForecastStoriesResponse(
        date=forecast.forecast_date,
        slides=[schemas.ForecastStorySlide(**slide) for slide in slides],
        llm_provider=llm_provider,
    )
