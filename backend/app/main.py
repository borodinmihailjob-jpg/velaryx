from contextlib import asynccontextmanager
import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .config import settings
from .localization import localize_json_bytes
from .routers import forecast, health, natal, tarot, telemetry
try:
    from .routers import geo
except ImportError:  # pragma: no cover
    geo = None


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("astrobot.api")


def _truncate(text: str, limit: int = 900) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [truncated]"


def _body_preview(raw: bytes, content_type: str) -> str:
    if not raw:
        return "-"
    if "application/json" in content_type:
        try:
            parsed = json.loads(raw.decode("utf-8"))
            return _truncate(json.dumps(parsed, ensure_ascii=False, separators=(",", ":")))
        except Exception:
            return _truncate(raw.decode("utf-8", errors="replace"))
    return f"<{len(raw)} bytes; {content_type or 'unknown'}>"


class ApiAuditAndLocalizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = uuid4().hex[:8]
        started_at = time.perf_counter()

        request_content_type = request.headers.get("content-type", "")
        request_body = await request.body()
        request_preview = _body_preview(request_body, request_content_type)

        method = request.method
        path = request.url.path
        query = request.url.query
        full_path = f"{path}?{query}" if query else path
        tg_user_id = request.headers.get("x-tg-user-id") or "-"
        auth_mode = "telegram" if request.headers.get("x-telegram-init-data") else "dev/internal"

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.exception(
                "API %s %s | status=500 | user=%s | auth=%s | t=%.1fms | req=%s | req_id=%s",
                method,
                full_path,
                tg_user_id,
                auth_mode,
                elapsed_ms,
                request_preview,
                request_id,
            )
            raise

        response_content_type = response.headers.get("content-type", "")
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        localized_body = response_body
        if (
            settings.enable_response_localization
            and response.status_code not in (204, 304)
            and "application/json" in response_content_type
        ):
            localized_body = localize_json_bytes(response_body)

        response_preview = _body_preview(localized_body, response_content_type)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "API %s %s | status=%s | user=%s | auth=%s | t=%.1fms | req=%s | resp=%s | req_id=%s",
            method,
            full_path,
            response.status_code,
            tg_user_id,
            auth_mode,
            elapsed_ms,
            request_preview,
            response_preview,
            request_id,
        )

        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        return Response(
            content=localized_body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )


logging.getLogger("uvicorn.access").disabled = True
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logging.getLogger("aiogram.dispatcher").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="AstroBot API", version="0.2.0", lifespan=lifespan)
app.add_middleware(ApiAuditAndLocalizationMiddleware)

if settings.cors_origins():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health.router)
if geo is not None:
    app.include_router(geo.router)
app.include_router(natal.router)
app.include_router(forecast.router)
app.include_router(tarot.router)
app.include_router(telemetry.router)
