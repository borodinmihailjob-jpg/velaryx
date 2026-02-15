from datetime import date, datetime, timedelta, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import models, schemas, services
from ..database import get_db
from ..dependencies import current_user_dep
from ..reporting import build_natal_report_pdf
from ..security import create_signed_token, verify_signed_token

router = APIRouter(prefix="/v1/reports", tags=["reports"])


@router.get("/natal.pdf")
def get_natal_pdf_report(
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    chart = services.get_latest_natal_chart(db=db, user_id=user.id)
    try:
        forecast = services.get_or_create_daily_forecast(db=db, user_id=user.id, forecast_date=date.today())
        forecast_payload = {
            "summary": forecast.summary,
            "energy_score": forecast.energy_score,
            "payload": forecast.payload,
        }
    except Exception:
        forecast_payload = None

    chart_payload = {
        "sun_sign": chart.sun_sign,
        "moon_sign": chart.moon_sign,
        "rising_sign": chart.rising_sign,
        "chart_payload": chart.chart_payload,
        "created_at": chart.created_at.isoformat(),
    }

    pdf_bytes = build_natal_report_pdf(
        user_id=user.tg_user_id,
        chart=chart_payload,
        forecast=forecast_payload,
    )

    filename = f"natal-report-{user.tg_user_id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/natal-link", response_model=schemas.ReportLinkResponse)
def get_natal_pdf_link(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user_dep),
):
    chart_exists = (
        db.query(models.NatalChart)
        .join(models.BirthProfile, models.BirthProfile.id == models.NatalChart.profile_id)
        .filter(models.BirthProfile.user_id == user.id)
        .first()
    )
    if not chart_exists:
        raise HTTPException(status_code=404, detail="Natal chart not found")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    token = create_signed_token(
        {
            "type": "natal_pdf",
            "tg_user_id": user.tg_user_id,
            "exp": int(expires_at.timestamp()),
        }
    )

    download_url = request.url_for("get_public_natal_pdf_report")
    return schemas.ReportLinkResponse(url=f"{download_url}?token={token}", expires_at=expires_at)


@router.get("/public/natal.pdf", name="get_public_natal_pdf_report")
def get_public_natal_pdf_report(
    token: str = Query(min_length=10),
    db: Session = Depends(get_db),
):
    payload = verify_signed_token(token)
    if not payload or payload.get("type") != "natal_pdf":
        raise HTTPException(status_code=401, detail="Invalid or expired report token")

    tg_user_id = payload.get("tg_user_id")
    if tg_user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(models.User).filter(models.User.tg_user_id == int(tg_user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    chart = services.get_latest_natal_chart(db=db, user_id=user.id)
    try:
        forecast = services.get_or_create_daily_forecast(db=db, user_id=user.id, forecast_date=date.today())
        forecast_payload = {
            "summary": forecast.summary,
            "energy_score": forecast.energy_score,
            "payload": forecast.payload,
        }
    except Exception:
        forecast_payload = None

    chart_payload = {
        "sun_sign": chart.sun_sign,
        "moon_sign": chart.moon_sign,
        "rising_sign": chart.rising_sign,
        "chart_payload": chart.chart_payload,
        "created_at": chart.created_at.isoformat(),
    }
    pdf_bytes = build_natal_report_pdf(
        user_id=user.tg_user_id,
        chart=chart_payload,
        forecast=forecast_payload,
    )
    filename = f"natal-report-{user.tg_user_id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
