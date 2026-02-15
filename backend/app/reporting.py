from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from textwrap import wrap
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas



def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").strip()



def _draw_wrapped(c: canvas.Canvas, text: str, x: int, y: int, max_chars: int = 95, line_height: int = 14) -> int:
    lines = wrap(_safe_text(text), width=max_chars) or [""]
    for line in lines:
        c.drawString(x, y, line)
        y -= line_height
    return y



def build_natal_report_pdf(*, user_id: int, chart: dict, forecast: dict | None = None) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    c.setTitle(f"AstroBot Natal Report {user_id}")
    c.setAuthor("AstroBot")

    y = height - 48
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "AstroBot - Natal Report")

    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Generated UTC: {datetime.now(timezone.utc).isoformat()}")
    y -= 16
    c.drawString(40, y, f"Telegram user id: {user_id}")

    y -= 26
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Core Signs")

    y -= 18
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Sun: {_safe_text(chart.get('sun_sign'))}")
    y -= 14
    c.drawString(40, y, f"Moon: {_safe_text(chart.get('moon_sign'))}")
    y -= 14
    c.drawString(40, y, f"Rising: {_safe_text(chart.get('rising_sign'))}")

    payload = chart.get("chart_payload") if isinstance(chart, dict) else {}
    interpretation = payload.get("interpretation") if isinstance(payload, dict) else {}

    y -= 24
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Interpretation")
    y -= 18
    c.setFont("Helvetica", 10)

    if isinstance(interpretation, dict):
        for key in ["summary", "sun_explanation", "moon_explanation", "rising_explanation"]:
            value = interpretation.get(key)
            if value:
                y = _draw_wrapped(c, _safe_text(value), 40, y)
                y -= 8
                if y < 90:
                    c.showPage()
                    c.setFont("Helvetica", 10)
                    y = height - 48

    key_aspects = interpretation.get("key_aspects") if isinstance(interpretation, dict) else []
    if isinstance(key_aspects, list) and key_aspects:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "Key Aspects")
        y -= 16
        c.setFont("Helvetica", 10)
        for aspect in key_aspects[:8]:
            y = _draw_wrapped(c, f"- {_safe_text(aspect)}", 48, y)
            if y < 90:
                c.showPage()
                c.setFont("Helvetica", 10)
                y = height - 48

    if forecast:
        y -= 16
        if y < 120:
            c.showPage()
            y = height - 48
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "Daily Forecast")
        y -= 18
        c.setFont("Helvetica", 10)
        y = _draw_wrapped(c, _safe_text(forecast.get("summary")), 40, y)

    c.showPage()
    c.save()
    return buffer.getvalue()
