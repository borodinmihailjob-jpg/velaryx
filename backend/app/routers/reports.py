from datetime import date
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import models, services
from ..database import get_db
from ..dependencies import current_user_dep
from ..reporting import build_natal_report_pdf

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
